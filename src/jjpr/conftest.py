import contextlib
import json
import logging
import os
import shutil
import tempfile
import typing as t
from pathlib import Path

import pytest
from filelock import FileLock

from .utils.exec import run as run_cmd

log = logging.getLogger(__name__)


@contextlib.contextmanager
def tmp_cwd() -> t.Generator[Path, None, None]:
    """Create a temporary working directory for tests."""
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_cwd_")
    original_dir = os.getcwd()
    os.chdir(tmp_dir)
    try:
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _create_dotfiles() -> None:
    # configure .gitrc
    run_cmd("git", "config", "set", "--global", "user.email", "test@example.com")
    run_cmd("git", "config", "set", "--global", "user.name", "Test User")

    # configure jj
    run_cmd("jj", "config", "set", "--user", "user.email", "test@example.com")
    run_cmd("jj", "config", "set", "--user", "user.name", "Test User")
    run_cmd(
        "jj",
        "config",
        "set",
        "--user",
        "aliases.pr",
        json.dumps(["util", "exec", "--", shutil.which("jj-pr")]),
    )


@pytest.fixture(scope="class")
def tmp_home() -> t.Generator[Path, None, None]:
    """Create a temporary home directory for tests, with git & jj configured."""
    original_home = os.environ.get("HOME", "")
    with tmp_cwd() as tmp_dir:
        try:
            os.environ["HOME"] = str(tmp_dir)
            os.environ["GIT_TERMINAL_PROMPT"] = "0"  # Disable git credential prompts
            home_lock = Path(tmp_dir) / ".jjpr-lock"
            with FileLock(home_lock):
                _create_dotfiles()

            yield Path(tmp_dir)
        finally:
            os.environ["HOME"] = original_home


@pytest.fixture
def tmp_repo(tmp_home: Path) -> t.Generator[Path, None, None]:
    with tmp_cwd() as remote_dir:
        run_cmd("git", "init", "--bare", "-b", "main")
        with tmp_cwd() as tmp_dir:
            run_cmd("git", "clone", str(remote_dir), ".")
            # a commit needs to exist before remote:HEAD exists
            run_cmd("git", "commit", "--allow-empty", "-m", "Initial commit")
            run_cmd("git", "push", "origin", "HEAD:main")
            run_cmd("jj", "git", "init", ".")
            run_cmd("jj", "bookmark", "track", "main", "--remote=origin")
            yield Path(tmp_dir)


@pytest.fixture
def repo_with_commits(tmp_repo: Path) -> t.Generator[Path, None, None]:
    Path("file1.txt").write_text("commit 1 content")
    run_cmd("jj", "commit", "-m", "Commit 1")

    Path("file2.txt").write_text("commit 2 content")
    run_cmd("jj", "bookmark", "create", "feat/commit-2")
    run_cmd("jj", "commit", "-m", "Commit 2")

    Path("file3.txt").write_text("commit 3 content")
    run_cmd("jj", "bookmark", "create", "feat/commit-3")
    run_cmd("jj", "commit", "-m", "Commit 3")

    yield tmp_repo
