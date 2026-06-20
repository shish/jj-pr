import logging
from pathlib import Path

import pytest

from jjpr import jj

from .conftest import run_cmd

log = logging.getLogger(__name__)


class TestRun:
    def test_basic_command(self, tmp_repo: Path):
        output = jj.run("log", "-r", "@", "--no-graph", "-T", "''")
        assert output is not None
        assert isinstance(output, str)

    def test_invalid_command(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.run("invalid-command-xyz")


class TestChangeid:
    def test_current(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        assert change_id
        assert len(change_id) > 0
        # Change IDs are short hashes
        assert isinstance(change_id, str)

    def test_root(self, repo_with_commits: Path):
        change_id = jj.change_id("root()")
        assert change_id
        assert isinstance(change_id, str)

    def test_invalid_revset(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.change_id("invalid::revset:::xyz")


class TestClosestWork:
    def test_multiple_commits(self, repo_with_commits: Path):
        change_id = jj.closest_work()
        assert change_id
        assert isinstance(change_id, str)

    def test_no_work(self, tmp_repo: Path):
        run_cmd("jj", "new", "trunk()")
        with pytest.raises(ValueError):  # "@ does not resolve to a single change ID"
            jj.closest_work()


class TestCurrentStack:
    def test_with_commits(self, repo_with_commits: Path):
        stack = jj.current_stack()
        assert isinstance(stack, list)
        assert len(stack) >= 3

    def test_returns_list(self, repo_with_commits: Path):
        stack = jj.current_stack()
        assert isinstance(stack, list)
        for item in stack:
            assert isinstance(item, str)

    def test_require_description(self, repo_with_commits: Path):
        stack = jj.current_stack(require_description=True)
        assert isinstance(stack, list)


class TestParentsOf:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.current_stack()
        if len(stack) > 1:
            change_id = stack[1]
            parents = jj.parents_of(change_id)
            assert isinstance(parents, list)
            assert len(parents) > 0

    def test_initial_commit(self, repo_with_commits: Path):
        root_id = jj.change_id("root()")
        parents = jj.parents_of(root_id)
        assert isinstance(parents, list)


class TestFilesIn:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.current_stack()
        if stack:
            change_id = stack[-1]
            files = jj.files_in(change_id)
            assert isinstance(files, list)
            assert len(files) > 0

    def test_files_in_commit_no_files(self, repo_with_commits: Path):
        run_cmd("jj", "new")
        current = jj.change_id("@")
        files = jj.files_in(current)
        assert isinstance(files, list)
        assert len(files) == 0


class TestBranchesPointingTo:
    def test_with_bookmarks(self, repo_with_commits: Path):
        changes = jj.current_stack()
        branches = jj.branches_pointing_to(changes[-1])
        assert isinstance(branches, list)

    def test_with_prefix(self, repo_with_commits: Path):
        changes = jj.current_stack()
        branches = jj.branches_pointing_to(changes[-1], prefix="feat/")
        assert isinstance(branches, list)

    def test_branches_pointing_to_no_branches(self, tmp_repo: Path):
        current = jj.change_id("@")
        branches = jj.branches_pointing_to(current)
        assert isinstance(branches, list)


class TestDescriptionOf:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.current_stack()
        change_id = stack[0]
        description = jj.description_of(change_id)
        assert isinstance(description, str)
        assert len(description) > 0
        # Should contain the commit message we set
        assert "Commit" in description or "Initial" in description


class TestWithEdit:
    def test_switches_to_commit(self, repo_with_commits: Path):
        stack = jj.current_stack()
        run_cmd("jj", "edit", "@-")  # be on the most recent not-empty commit
        original = jj.change_id("@")

        assert len(stack) > 1
        target = stack[0]
        with jj.with_edit(target):
            assert jj.change_id("@") == target

        assert jj.change_id("@") == original

    def test_no_op_when_already_on_target(self, repo_with_commits: Path):
        current = jj.change_id("@")

        with jj.with_edit(current):
            during = jj.change_id("@")
            assert during == current

        after = jj.change_id("@")
        assert after == current

    def test_preserves_empty_commit(self, repo_with_commits: Path):
        run_cmd("jj", "new")
        stack = jj.current_stack()
        assert len(stack) > 1

        target = stack[0]
        original = jj.change_id("@")
        assert jj.files_in(original) == []  # Ensure original is empty
        original_parents = jj.parents_of(original)

        with jj.with_edit(target):
            assert jj.change_id("@") == target

        replacement = jj.change_id("@")
        assert jj.files_in(replacement) == []  # Ensure we return to empty
        assert jj.parents_of(replacement) == original_parents


class TestWithNew:
    def test_creates_new_commit(self, repo_with_commits: Path):
        stack = jj.current_stack()
        original_parents = jj.parents_of("@")

        assert len(stack) > 1
        target = stack[0]
        with jj.with_new(target):
            assert jj.parents_of("@") == [target]

        assert jj.parents_of("@") == original_parents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
