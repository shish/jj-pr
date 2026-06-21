import os
from pathlib import Path
from unittest import mock

import httpx
import pytest

from . import cmds
from .conftest import tmp_cwd
from .forges.base import CRListItem


def make_cr_list_item(
    forge_name: str = "TestForge",
    forge_url: httpx.URL | None = None,
    project_id: str = "test-project",
    identifier: str = "123",
    title: str = "Test Item",
    url: httpx.URL | None = None,
    state: str = "Open",
    blockers: str = "",
    extra: dict[str, str] | None = None,
) -> CRListItem:
    """Create a CRListItem with sensible defaults for testing."""
    if forge_url is None:
        forge_url = httpx.URL("https://test.example.com")
    if url is None:
        url = httpx.URL(f"https://test.example.com/item/{identifier}")
    if extra is None:
        extra = {}
    return CRListItem(
        forge_name=forge_name,
        forge_url=forge_url,
        project_id=project_id,
        identifier=identifier,
        title=title,
        url=url,
        state=state,
        blockers=blockers,
        extra=extra,
    )


class TestRepo:
    def test_init(self, tmp_repo: Path):
        r = cmds.Repo(tmp_repo, "origin", "github")
        assert r.path == tmp_repo
        with tmp_cwd() as _:
            assert os.getcwd() != str(tmp_repo)
            with r.chdir():
                assert os.getcwd() == str(tmp_repo)


class TestGetPcCommand:
    def test_no_hook_configured(self):
        """Test _get_pc_command when no pre-commit hook is found."""
        with tmp_cwd():
            result = cmds._get_pc_command()
            assert result is None

    def test_hook_exists_prek_available(self):
        """Test _get_pc_command when hook exists and prek is available."""
        with tmp_cwd():
            # Create .git/hooks/pre-commit
            Path(".git/hooks").mkdir(parents=True, exist_ok=True)
            Path(".git/hooks/pre-commit").touch()

            with mock.patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/bin/prek"
                result = cmds._get_pc_command()
                assert result == "/usr/bin/prek"

    def test_hook_exists_precommit_available(self):
        """Test _get_pc_command when hook exists and pre-commit is available."""
        with tmp_cwd():
            # Create .git/hooks/pre-commit
            Path(".git/hooks").mkdir(parents=True, exist_ok=True)
            Path(".git/hooks/pre-commit").touch()

            with mock.patch("shutil.which") as mock_which:

                def which_side_effect(cmd):
                    if cmd == "prek":
                        return None
                    elif cmd == "pre-commit":
                        return "/usr/bin/pre-commit"
                    return None

                mock_which.side_effect = which_side_effect
                result = cmds._get_pc_command()
                assert result == "/usr/bin/pre-commit"

    def test_hook_exists_no_binary(self):
        """Test _get_pc_command when hook exists but no binary available."""
        with tmp_cwd():
            # Create .git/hooks/pre-commit
            Path(".git/hooks").mkdir(parents=True, exist_ok=True)
            Path(".git/hooks/pre-commit").touch()

            with mock.patch("shutil.which", return_value=None):
                result = cmds._get_pc_command()
                assert result is None


class TestGetArcCommand:
    def test_no_arclint_configured(self):
        """Test _get_arc_command when no .arclint file is found."""
        with tmp_cwd():
            result = cmds._get_arc_command()
            assert result is None

    def test_arclint_exists_arc_available(self):
        """Test _get_arc_command when .arclint exists and arc is available."""
        with tmp_cwd():
            Path(".arclint").touch()

            with mock.patch("shutil.which", return_value="/usr/bin/arc"):
                result = cmds._get_arc_command()
                assert result == "/usr/bin/arc"

    def test_arclint_exists_no_arc_binary(self):
        """Test _get_arc_command when .arclint exists but arc binary not found."""
        with tmp_cwd():
            Path(".arclint").touch()

            with mock.patch("shutil.which", return_value=None):
                result = cmds._get_arc_command()
                assert result is None


class TestPreCommitStack:
    def test_no_hooks_configured(self, tmp_repo: Path):
        """Test pre_commit when no hooks are configured."""
        # Should not raise and should return early
        with mock.patch("jjpr.cmds.pre_commit_change") as pcc:
            cmds.pre_commit_stack(None)
            assert not pcc.called

    def test_with_pc_hook(self, repo_with_commits: Path):
        """Test pre_commit with pre-commit hook configured."""
        # Create .git/hooks/pre-commit
        Path(".git/hooks").mkdir(parents=True, exist_ok=True)
        Path(".git/hooks/pre-commit").touch()

        # Mock shutil.which to return a valid prek path and mock exec.run to avoid actual execution
        with mock.patch("shutil.which") as mock_which:
            with mock.patch("jjpr.cmds.pre_commit_change") as pcc:
                mock_which.return_value = "/usr/bin/prek"
                cmds.pre_commit_stack(None)
                assert pcc.called

    def test_with_arc_hook(self, repo_with_commits: Path):
        """Test pre_commit with arc linter configured."""
        # Create .arclint
        Path(".arclint").touch()

        # Mock shutil.which and exec.run
        with mock.patch("shutil.which") as mock_which:
            with mock.patch("jjpr.cmds.pre_commit_change") as pcc:
                mock_which.return_value = "/usr/bin/arc"
                cmds.pre_commit_stack(None)
                assert pcc.called


class TestPreCommitChange:
    def test_pre_commit_change_ok(self, repo_with_commits: Path):
        cmds.pre_commit_change("@-", "echo", "echo")

    def test_pre_commit_change_fail(self, repo_with_commits: Path):
        with pytest.raises(Exception):
            cmds.pre_commit_change("@-", "true", "false")


class TestDisplayList:
    def test_display_list_multi(self):
        """Test display_list with multiple items from same forge."""
        items = [
            make_cr_list_item(identifier="123", title="Fix bug"),
            make_cr_list_item(
                identifier="124",
                title="Add feature",
                state="In Review",
                blockers="Needs approval",
                extra={"Attachments": "42"},
            ),
        ]
        cmds.display_list(items, multi=True)

    def test_display_list_empty(self):
        """Test display_list with no items."""
        cmds.display_list([], multi=False)

    def test_display_list_single_item(self):
        """Test display_list with single item."""
        items = [make_cr_list_item(identifier="123", title="Fix bug")]
        cmds.display_list(items, multi=False)

    def test_display_list_multi_forge_urls(self):
        """Test display_list with items from multiple forges."""
        items = [
            make_cr_list_item(
                forge_name="GitHubForge",
                forge_url=httpx.URL("https://github.com"),
                project_id="proj1",
                identifier="123",
                title="Feature 1",
                url=httpx.URL("https://github.com/repo/123"),
                state="Open",
            ),
            make_cr_list_item(
                forge_name="GerritForge",
                forge_url=httpx.URL("https://gerrit.example.com"),
                project_id="proj2",
                identifier="456",
                title="Fix 1",
                url=httpx.URL("https://gerrit.example.com/change/456"),
                state="Reviewing",
            ),
        ]
        cmds.display_list(items, multi=True)

    def test_display_list_with_extra_fields(self):
        """Test display_list with extra fields in items."""
        items = [
            make_cr_list_item(
                identifier="789",
                title="Task",
                state="In Progress",
                blockers="Waiting",
                extra={"Priority": "High", "Assignee": "John"},
            ),
            make_cr_list_item(
                identifier="790",
                title="Another Task",
                state="Done",
                extra={"Priority": "Low"},
            ),
        ]
        cmds.display_list(items, multi=True)
