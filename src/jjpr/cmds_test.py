import os
from pathlib import Path
from unittest import mock

import httpx
import pytest

from . import cmds
from .conftest import run_cmd, tmp_cwd
from .forges import cr
from .forges.base import Forge
from .forges.demo.forge import Demo


def make_cr_list_item(
    forge: Forge = Demo("origin"),
    cr_id: str = "123",
    title: str = "Test Item",
    url: httpx.URL | None = None,
    state: cr.State = cr.State("Open", color="cyan"),
    checks: list[cr.Blocker] = [],
    blockers: list[cr.Blocker] = [],
    extra: dict[str, str] | None = None,
) -> cr.CodeReview:
    """Create a CRListItem with sensible defaults for testing."""
    if url is None:
        url = httpx.URL(f"https://test.example.com/item/{cr_id}")
    if extra is None:
        extra = {}
    return cr.CodeReview(
        forge=forge,
        cr_id=cr_id,
        title=cr.Title(title, url=url),
        state=state,
        checks=checks,
        blockers=blockers,
        extra=extra,
    )


class TestRepo:
    def test_init(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://github.com/shish/jj-pr")
        r = cmds.Repo(tmp_repo, None)
        assert r.path == tmp_repo
        with tmp_cwd() as _:
            assert os.getcwd() != str(tmp_repo)
            with r.chdir():
                assert os.getcwd() == str(tmp_repo)


class TestPreCommitStack:
    def test_no_hooks_configured(self, tmp_repo: Path):
        # Should not raise and should return early
        with mock.patch("jjpr.cmds.pre_commit_change") as pcc:
            cmds.pre_commit_stack(None)
            assert not pcc.called

    def test_with_pc_hook(self, repo_with_commits: Path):
        # Create .git/hooks/pre-commit
        Path(".git/hooks").mkdir(parents=True, exist_ok=True)
        Path(".git/hooks/pre-commit").touch()

        with mock.patch("jjpr.cmds.pre_commit_change") as pcc:
            cmds.pre_commit_stack(None)
            assert pcc.called


class TestPreCommitChange:
    def test_pre_commit_change_ok(self, repo_with_commits: Path):
        cmds.pre_commit_change("@-", "true")

    def test_pre_commit_change_fail(self, repo_with_commits: Path):
        with pytest.raises(Exception):
            cmds.pre_commit_change("@-", "false")


class TestDisplayList:
    def test_display_list_empty(self):
        cmds.display_list([])

    def test_display_list_single_item(self):
        items = [make_cr_list_item(cr_id="123", title="Fix bug")]
        cmds.display_list(items)

    def test_display_list_with_extra_fields(self):
        items = [
            make_cr_list_item(
                cr_id="789",
                title="Task",
                state=cr.State("In Progress", color="cyan"),
                blockers=[cr.Blocker(name="Waiting")],
                extra={"Priority": "High", "Assignee": "John"},
            ),
            make_cr_list_item(
                cr_id="790",
                title="Another Task",
                state=cr.State("Done", color="green"),
                extra={"Priority": "Low"},
            ),
        ]
        cmds.display_list(items)
