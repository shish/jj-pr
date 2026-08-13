import json
import logging
import random
import shutil
import string
import typing as t
from pathlib import Path

import httpx
import pytest

from ...conftest import run_cmd, tmp_cwd
from ...utils import netrc
from .lib import client

log = logging.getLogger(__name__)


@pytest.fixture(scope="class")
def url() -> httpx.URL:
    return httpx.URL("http://phab.localhost:8081")


@pytest.fixture(scope="class")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> t.Generator[client.PhabricatorClient, None, None]:
    # configure .arcrc
    data = {
        "hosts": {str(url) + "/api/": {"token": "cli-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}
    }
    rc = Path(tmp_home) / ".arcrc"
    rc.write_text(json.dumps(data))
    rc.chmod(0o600)

    netrc.write(url.host, "admin", "test")

    # configure http client with persistent token
    sess = client.PhabricatorClient(url)

    # check that the client works
    if not shutil.which("arc"):
        pytest.skip("`arc` command not found, skipping tests")
    try:
        data = sess.call("user.whoami")
        assert data["userName"] == "admin"
    except Exception as e:
        pytest.skip(f"Phabricator server seems broken, skipping tests: {e}")
    yield sess


@pytest.fixture
def repo_name() -> str:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    return f"ztst-{rand}"


@pytest.fixture
def repo(
    url: httpx.URL,
    repo_name: str,
    session: client.PhabricatorClient,
    request: pytest.FixtureRequest,
) -> t.Generator[httpx.URL, None, None]:
    callsign = f"ZTST{repo_name[-4:].upper()}"

    # Call the Phabricator API to create the metadata for
    # a new repository (but the actual repo is created by
    # a cronjob a minute or two later)
    try:
        session.call(
            "diffusion.repository.edit",
            transactions=[
                {"type": "name", "value": repo_name},
                {"type": "vcs", "value": "git"},
                {"type": "callsign", "value": callsign},
                {"type": "status", "value": "active"},
                {"type": "shortName", "value": repo_name},
            ],
        )

        # Force the repository to be created immediately, instead of waiting
        # for phabricator's internal cronjob to run and detect the metadata
        # we set above.
        original_dir = request.config.invocation_params.dir
        # fmt: off
        run_cmd(
            "docker", "compose", "-f", str(original_dir / "compose.yml"),
            "exec", "phabricator",
            "runuser", "-u", "www-data",
            "bin/repository", "update", callsign,
        )
        # fmt: on
    except Exception as e:
        pytest.skip(f"Phabricator repo creation error: {url}: {e}")

    try:
        repo_url = url.join(f"/source/{repo_name}.git")
        with tmp_cwd():
            run_cmd("git", "clone", str(repo_url), ".")
            # jj can't tell which branch is trunk() if we clone a totally bare repo,
            # so let's pre-populate an empty commit as part of the repo creation process.
            Path(".arcconfig").write_text(
                json.dumps({
                    "phabricator.uri": str(url),
                    "repository.callsign": callsign,
                })
            )
            run_cmd("git", "add", ".arcconfig")
            run_cmd("git", "commit", "-m", "Initial empty repository", "--allow-empty")
            run_cmd("git", "push")

        yield repo_url
    finally:
        response = session.call(
            "diffusion.repository.search",
            constraints={"shortNames": [repo_name]},
        )
        session.call(
            "diffusion.repository.edit",
            objectIdentifier=response["data"][0]["phid"],
            transactions=[{"type": "status", "value": "inactive"}],
        )


@pytest.fixture
def clone(repo: httpx.URL) -> t.Generator[Path, None, None]:
    with tmp_cwd() as tmp_dir:
        run_cmd("jj", "git", "clone", str(repo), ".")
        yield tmp_dir
