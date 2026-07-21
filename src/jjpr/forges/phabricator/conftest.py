import json
import logging
import os
import random
import shutil
import string
import typing as t
from pathlib import Path

import httpx
import pytest
import tenacity as tc

from ...conftest import run_cmd, tmp_cwd
from ...utils import netrc
from .client import PhabricatorClient

log = logging.getLogger(__name__)


@pytest.fixture(scope="class")
def url() -> httpx.URL:
    """Get the Phabricator URL from the environment variable or use a default."""
    return httpx.URL(
        os.getenv("JJPR_TEST_PHABRICATOR_URL", "http://phab.localhost:8081")
    )


@pytest.fixture(scope="class")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> t.Generator[PhabricatorClient, None, None]:
    # configure .arcrc
    phabricator_token = os.getenv("JJPR_TEST_PHABRICATOR_API_TOKEN")
    if not phabricator_token:
        pytest.skip("JJPR_TEST_PHABRICATOR_API_TOKEN not set, skipping tests")

    data = {"hosts": {str(url) + "/api/": {"token": phabricator_token}}}
    rc = Path(tmp_home) / ".arcrc"
    rc.write_text(json.dumps(data))
    rc.chmod(0o600)

    vcs_password = os.getenv("JJPR_TEST_PHABRICATOR_VCS_PASSWORD")
    if not vcs_password:
        pytest.skip("JJPR_TEST_PHABRICATOR_VCS_PASSWORD not set, skipping tests")

    netrc.write(url.host, "admin", vcs_password)

    # configure http client with persistent token
    client = PhabricatorClient(url)

    # check that the client works
    if not shutil.which("arc"):
        pytest.skip("`arc` command not found, skipping tests")
    try:
        data = client.call("user.whoami")
        assert data["userName"] == "admin"
    except Exception as e:
        pytest.skip(f"Phabricator server seems broken, skipping tests: {e}")
    yield client


@pytest.fixture
def repo(
    url: httpx.URL,
    session: PhabricatorClient,
    request: pytest.FixtureRequest,
) -> t.Generator[httpx.URL, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-phab-{rand}"
    callsign = f"ZTST{rand.upper()}"

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
    except Exception as e:
        pytest.skip(f"Phabricator repo creation error: {url}: {e}")

    # Force the repository to be created immediately
    try:
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
        pytest.skip(f"Phabricator repo update error: {url}: {e}")

    try:
        repo_url = url.join(f"/source/{repo_name}.git")
        with tmp_cwd():
            # Originally we waited for the repo to be created by the cronjob,
            # now we force it via the `bin/repository update` command above,
            # but leaving this here in case we want to test against a real
            # server without `docker compose` access in the future.
            for attempt in tc.Retrying(
                stop=tc.stop_after_attempt(60),
                wait=tc.wait_fixed(2),
                reraise=True,
            ):
                with attempt:
                    run_cmd("git", "clone", str(repo_url), ".")

            # jj can't tell which branch is trunk() if we clone a totally bare repo,
            # so let's pre-populate an empty commit as part of the repo creation process.
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
