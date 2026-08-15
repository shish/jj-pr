from pathlib import Path
from textwrap import dedent

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
        # Create a change and upload for review
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")
        assert jj.diagram() == dedent("""
            @
            o  Test commit 1
            +  Initial empty repository
        """)

        # While the change is being reviewed, `main` moves forwards
        with tmp_cwd() as admin_clone:
            run_cmd("jj", "git", "clone", str(repo), ".")
            (admin_clone / "main_advance.txt").write_text("Main advance content")
            run_cmd("jj", "describe", "-m", "Advance main")
            run_cmd("jj", "b", "a")
            run_cmd("jj", "git", "push")
            assert jj.diagram() == dedent("""
                @
                +  Advance main
            """)

        # Fetch to see the new main has moved forwards
        run_cmd("jj", "git", "fetch")
        assert jj.diagram() == dedent("""
            @
            o  Test commit 1
            | +  Advance main
            |/
            +  Initial empty repository
        """)

        # Rebase on top of the new main
        run_cmd("jj", "pr", "rebase")
        assert jj.diagram() == dedent("""
            @
            o  Test commit 1
            +  Advance main
        """)
