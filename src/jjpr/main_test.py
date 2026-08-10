from pathlib import Path
from unittest import mock

import pytest

from . import main
from .utils import exc, jj


class TestPreCommitStack:
    def test_no_hooks_configured(self, tmp_repo: Path):
        # Should not raise and should return early
        with mock.patch("jjpr.main._pre_commit_change") as pcc:
            main._pre_commit_stack(jj.checkable_stack())
            assert not pcc.called

    def test_with_pc_hook(self, repo_with_commits: Path):
        # Create .git/hooks/pre-commit
        Path(".git/hooks").mkdir(parents=True, exist_ok=True)
        Path(".git/hooks/pre-commit").touch()

        with mock.patch("jjpr.main._pre_commit_change") as pcc:
            main._pre_commit_stack(jj.checkable_stack())
            assert pcc.called


class TestPreCommitChange:
    def test_pre_commit_change_ok(self, repo_with_commits: Path):
        main._pre_commit_change(jj.change_id("@-"), "true")

    def test_pre_commit_change_fail(self, repo_with_commits: Path):
        with pytest.raises(exc.UserError):
            main._pre_commit_change(jj.change_id("@-"), "false")
