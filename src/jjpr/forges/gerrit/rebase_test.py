from pathlib import Path

import httpx
import pytest

from ...conftest import run_cmd, tmp_cwd
from ...utils import jj

pytestmark = [pytest.mark.integration, pytest.mark.gerrit]


class TestRebase:
    def test_rebase_with_private_changes(self, clone: Path):
        output = run_cmd("jj", "pr", "rebase")
        assert "Rebasing" in output

    def test_rebase_with_uploaded_changes(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        output = run_cmd("jj", "pr", "rebase")
        assert "Rebasing" in output

    def test_rebase_onto_updated_main(self, clone: Path, repo: httpx.URL):
        pytest.skip(
            "Skipping test because I can't figure out how to allow pushing "
            "direct to `main` on the test repo o.o"
        )

        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        with tmp_cwd() as admin_clone:
            run_cmd("git", "clone", str(repo), ".")
            (admin_clone / "main_advance.txt").write_text("Main advance content")
            run_cmd("git", "add", ".")
            run_cmd("git", "commit", "-m", "Advance main")
            run_cmd("git", "push", "origin", "HEAD:refs/heads/main", cap=False)

        run_cmd("jj", "git", "fetch", "origin")
        output = run_cmd("jj", "pr", "rebase")
        assert "Rebasing" in output
        assert jj.description_of("@") == "Test commit 1"
        assert jj.description_of("@-") == "Advance main"
