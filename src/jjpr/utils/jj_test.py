import logging
import os
from pathlib import Path
from textwrap import dedent
from unittest import mock

import httpx
import pytest

from ..conftest import run_cmd
from . import cr, jj, text

log = logging.getLogger(__name__)


class TestUtils:
    def test_run_basic_command(self, tmp_repo: Path):
        output = jj.run("log", "-r", "@", "--no-graph", "-T", "''")
        assert output is not None
        assert isinstance(output, str)

    def test_run_invalid_command(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.run("invalid-command-xyz")


class TestDirectMappings:
    def test_bookmark_create_and_advance(self, repo_with_commits: Path):
        change_id = jj.change_id("@-")
        bookmark_name = "test-bookmark"

        # Create a bookmark pointing to the previous change
        jj.bookmark_create(bookmark_name, change_id)
        bookmarks = jj.bookmarks()
        assert bookmark_name in bookmarks

        # Advance the bookmark to the current change
        change_id = jj.change_id("@")
        jj.bookmark_advance(bookmark_name, change_id)
        bookmarks_after_advance = jj.bookmarks()
        assert bookmark_name in bookmarks_after_advance

    def test_bookmark_track(self, repo_with_commits: Path):
        bookmark_name = "test-bookmark"
        remote_name = "origin"

        # Create a bookmark pointing to the current change
        change_id = jj.change_id("@")
        jj.bookmark_create(bookmark_name, change_id)

        # Track the bookmark with the specified remote
        jj.bookmark_track(bookmark_name, remote_name)
        bookmarks = jj.bookmarks()
        assert f"{bookmark_name}@{remote_name}" in bookmarks

    def test_commit(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.commit("my message")
            mock_run.assert_called_once_with("commit", "-m", "my message", cap=False)

    def test_edit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        target = stack[0]
        jj.edit(target)
        assert jj.change_id("@") == target

    def test_new(self, repo_with_commits: Path):
        parent = jj.change_id("@")
        jj.new("@")
        assert jj.parents_of(jj.change_id("@")) == {parent}

    def test_config_get(self, repo_with_commits: Path):
        # Set a config value
        jj.run("config", "set", "--repo", "test.key", "test_value")
        value = jj.config_get("test.key")
        assert value == "test_value"

        # Test getting a non-existent config key
        non_existent_value = jj.config_get("non.existent.key")
        assert non_existent_value is None

    def test_describe(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        new_description = "Updated description"
        jj.describe(change_id, new_description)
        description = jj.description_of(change_id)
        assert new_description in description

    def test_gerrit_upload_basic(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        with mock.patch("jjpr.utils.jj.run"):
            jj.gerrit_upload(remote="origin", r=change_id)

    def test_gerrit_upload_with_all_options(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.gerrit_upload(
                remote="origin",
                r=change_id,
                wip=True,
                message="Test",
                remote_branch="refs/for/main",
            )
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "gerrit" in args
            assert "--wip" in args
            assert "--message" in args
            assert "Test" in args
            assert "--remote-branch" in args
            assert "refs/for/main" in args

    def test_git_fetch(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.git_fetch("origin")
            mock_run.assert_called_once_with(
                "git", "fetch", "--remote", "origin", cap=False
            )
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.git_fetch(all_remotes=True)
            mock_run.assert_called_once_with("git", "fetch", "--all-remotes", cap=False)

    def test_git_push(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.git_push("origin", "main")
            mock_run.assert_called_once_with(
                "git", "push", "--remote", "origin", "--bookmark", "main", cap=False
            )

    def test_rebase(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.rebase(d="trunk()", r="@")
            mock_run.assert_called_once_with(
                "rebase", "--skip-emptied", "-d", "trunk()", "-r", "@", cap=False
            )
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.rebase(d="trunk()", s="@")
            mock_run.assert_called_once_with(
                "rebase", "--skip-emptied", "-d", "trunk()", "-s", "@", cap=False
            )

    def test_root(self, repo_with_commits: Path):
        assert os.getcwd() == str(jj.root())


class TestChangeInfo:
    def test_parents_of_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        assert len(stack) > 1
        assert jj.parents_of(stack[1]) == {stack[0]}

    def test_parents_of_root(self, repo_with_commits: Path):
        assert jj.parents_of(jj.change_id("root()")) == set()

    def test_files_in_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        change_id = stack[1]
        files = jj.files_in(change_id)
        assert files == {"file2.txt"}

    def test_files_in_commit_no_files(self, repo_with_commits: Path):
        run_cmd("jj", "new")
        assert jj.files_in(jj.change_id("@")) == set()

    def test_description_of_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        change_id = stack[0]
        description = jj.description_of(change_id)
        assert "Commit" in description or "Initial" in description

    def test_branches_pointing_to_with_bookmarks(self, repo_with_commits: Path):
        c = jj.change_id("feat/commit-2")
        branches = jj.branches_pointing_to(c)
        assert branches == {"feat/commit-2"}

    def test_branches_pointing_to_with_prefix(self, repo_with_commits: Path):
        c = jj.change_id("feat/commit-2")
        branches = jj.branches_pointing_to(c, prefix="feat/")
        assert branches == {"feat/commit-2"}
        branches = jj.branches_pointing_to(c, prefix="pr/")
        assert branches == set()

    def test_branches_pointing_to_no_branches(self, tmp_repo: Path):
        current = jj.change_id("root()")
        branches = jj.branches_pointing_to(current)
        assert branches == set()

    def test_commit_id(self, repo_with_commits: Path):
        commit_id = jj.commit_id(jj.change_id("@"))
        assert len(commit_id) == 40  # SHA-1 hash length


class TestChangeId:
    def test_current(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        assert len(change_id) > 0
        # Change IDs are short hashes
        assert isinstance(change_id, str)

    def test_root(self, repo_with_commits: Path):
        change_id = jj.change_id("root()")
        assert change_id == "z" * 32

    def test_invalid_revset(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.change_id("invalid::revset:::xyz")

    def test_multiple_matches(self, repo_with_commits: Path):
        with pytest.raises(ValueError):
            jj.change_id("trunk()..@")


class TestClosestWork:
    def test_multiple_commits(self, repo_with_commits: Path):
        change_id = jj.closest_work()
        assert change_id
        assert isinstance(change_id, str)

    def test_no_work(self, tmp_repo: Path):
        run_cmd("jj", "new", "trunk()")
        with pytest.raises(ValueError):  # "@ does not resolve to a single change ID"
            jj.closest_work()


class TestPushableStack:
    def test_require_description(self, repo_with_commits: Path):
        stack = jj.pushable_stack()
        assert isinstance(stack, list)
        assert len(stack) >= 3


class TestCheckableStack:
    def test_with_commits(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        assert isinstance(stack, list)
        assert len(stack) >= 3


class TestBookmarks:
    def test_bookmarks_basic(self, repo_with_commits: Path):
        bookmarks = jj.bookmarks()
        assert isinstance(bookmarks, dict)
        assert "main" in bookmarks

    def test_bookmarks_with_remote(self, repo_with_commits: Path):
        # remote bookmarks only show up when they differ from local?
        jj.bookmark_create("mywork", r="root()+")
        jj.git_push("origin", "mywork")
        jj.bookmark_advance("mywork", "@-")
        bookmarks = jj.bookmarks()
        assert "mywork@origin" in bookmarks


class TestLogWithAnnotations:
    def test_log(self) -> None:
        log_output = (
            "@  psnykstn shish@shishnet.org 09:07:34 148e97e0 JJPR::JJPR\n"
            "│  (empty) (no description set)\n"
            "○  sxuvxvpr shish@shishnet.org 09:07:34 c790cc63 JJPR:D123:JJPR\n"
            "│  yay\n"
            "○  kpromlsy shish@shishnet.org 07:32:46 a52fe356 JJPR:D456:JJPR\n"
            "│  update\n"
            "◆  lltxxqkq shish@shishnet.org 00:35:10 master master@origin bf993ebb \n"
            "│  initial import\n"
            "~\n"
        )
        with mock.patch.object(jj, "run", return_value=log_output):
            txt = jj.log_with_annotations(
                [],
                "commit.pr_id()",
                lambda pr_ids: {
                    "D123": cr.CodeReview(
                        cr_id="456",
                        title="Fix bug",
                        url=httpx.URL("https://example.com/fix-bug"),
                        state=cr.ReviewState(name="Accepted", color="green"),
                        checks=[],
                        extra={"author": "alice", "branch": "feature/x"},
                    ),
                    "D456": cr.CodeReview(
                        cr_id="456",
                        title="Fix bug",
                        url=httpx.URL("https://example.com/fix-bug"),
                        state=cr.ReviewState(name="Needs Review", color="yellow"),
                        checks=[],
                        extra={"author": "alice", "branch": "feature/x"},
                    ),
                },
            )

        assert text.remove_ansi(txt) == (
            "@  psnykstn shish@shishnet.org 09:07:34 148e97e0 \n"
            "│  (empty) (no description set)\n"
            "○  sxuvxvpr shish@shishnet.org 09:07:34 c790cc63 Accepted\n"
            "│  yay\n"
            "○  kpromlsy shish@shishnet.org 07:32:46 a52fe356 Needs Review\n"
            "│  update\n"
            "◆  lltxxqkq shish@shishnet.org 00:35:10 master master@origin bf993ebb \n"
            "│  initial import\n"
            "~\n"
        )

    def test_example(
        self,
        tmp_repo: Path,
        request: pytest.FixtureRequest,
    ) -> None:
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        run_cmd(
            "jj", "config", "set", "--repo", "templates.log", "builtin_log_comfortable"
        )
        run_cmd(
            "jj",
            "config",
            "set",
            "--repo",
            "template-aliases.'format_short_signature(signature)'",
            "'signature.email().local()'",
        )
        run_cmd(
            "jj",
            "config",
            "set",
            "--repo",
            "template-aliases.'format_timestamp(timestamp)'",
            'timestamp.format("%H:%M:%S")',
        )
        run_cmd("jj", "config", "set", "--repo", "user.email", "shish@example.com")

        commits = {}

        def commit(message: str, state: str) -> None:
            (tmp_repo / "file.txt").write_text(message)
            jj.commit(m=message)
            commits[message] = {
                "id": jj.change_id("@"),
                "state": text.rich_str(state),
            }

        (tmp_repo / "file.txt").write_text("bah")
        jj.commit(m="Release 0.1")
        jj.bookmark_advance("main", "@-")
        jj.git_push("origin", "main")

        tick = "[green][link=http://demo]✔[/link][/green]"
        cross = "[red][link=http://demo]✗ (formatting)[/link][/red]"
        dot = "[yellow][link=http://demo]…[/link][/yellow]"
        accepted = "[green][link=http://demo]Accepted[/link][/green]"
        review = "[yellow][link=http://demo]Needs Review[/link][/yellow]"
        # changes = "[red][link=http://demo]Needs Changes[/link][/red]"
        draft = "[cyan][link=http://demo]Changes Planned[/link][/cyan]"

        base = jj.change_id("@-")
        commit("Add GraphQL client", f"{accepted} {tick} {tick} {tick}")
        commit("Use GraphQL instead of subprocess", f"{review} {tick} {dot} {tick}")

        jj.new(base)
        commit("Speed up integration tests", f"{accepted} {cross} {tick} {tick}")
        commit("Add more test coverage", f"{draft} {dot} {tick} {tick}")

        jj.edit(jj.change_id("@-"))
        data = jj.log_with_annotations(
            [],
            "commit.description().first_line()",
            lambda pr_ids: {
                pr_id: commits.get(pr_id, {}).get("state", "") for pr_id in pr_ids
            },
        )

        p = request.config.invocation_params.dir / ".github" / "log-demo.ansi"
        if not p.exists():
            lines = data.splitlines()
            lines = [f"  {line}" for line in lines]
            data = "\n".join(lines)
            p.write_text(f"\n{data}\n\n")


class TestWithEdit:
    def test_no_op_when_already_on_target(self, repo_with_commits: Path):
        jj.edit(jj.change_id("@-"))

        assert jj.diagram() == dedent("""
            @  Commit 3
            o  Commit 2
            o  Commit 1
            +  Initial commit
        """)

        # edit itself
        with jj.with_edit(jj.change_id("@")):
            assert jj.diagram() == dedent("""
                @  Commit 3
                o  Commit 2
                o  Commit 1
                +  Initial commit
            """)

        # still on itself
        assert jj.diagram() == dedent("""
            @  Commit 3
            o  Commit 2
            o  Commit 1
            +  Initial commit
        """)

    def test_switches_to_commit(self, repo_with_commits: Path):
        jj.edit(jj.change_id("@--"))

        # Start in the middle of the stack
        assert jj.diagram() == dedent("""
            o  Commit 3
            @  Commit 2
            o  Commit 1
            +  Initial commit
        """)

        # Edit the top of the stack
        with jj.with_edit("@+"):
            assert jj.diagram() == dedent("""
                @  Commit 3
                o  Commit 2
                o  Commit 1
                +  Initial commit
            """)

        # Check that we returned to the original commit
        assert jj.diagram() == dedent("""
            o  Commit 3
            @  Commit 2
            o  Commit 1
            +  Initial commit
        """)

    def test_preserves_empty_commit(self, repo_with_commits: Path):
        # start from an empty fork off of a non-empty commit in the middle of the stack
        stack = jj.pushable_stack()
        run_cmd("jj", "new", stack[-2])
        original = jj.change_id("@")
        assert jj.diagram() == dedent("""
            @
            | o  Commit 3
            |/
            o  Commit 2
            o  Commit 1
            +  Initial commit
        """)

        # edit some other part of the stack
        target = stack[-1]
        with jj.with_edit(target):
            assert jj.diagram() == dedent("""
                @  Commit 3
                o  Commit 2
                o  Commit 1
                +  Initial commit
            """)

        # return to a new empty forked off of the same point
        replacement = jj.change_id("@")
        assert replacement != original
        assert jj.diagram() == dedent("""
            @
            | o  Commit 3
            |/
            o  Commit 2
            o  Commit 1
            +  Initial commit
        """)


class TestWithNew:
    def test_creates_new_commit(self, repo_with_commits: Path):
        # Starting in the middle of the stack
        jj.edit(jj.change_id("@--"))
        assert jj.diagram() == dedent("""
            o  Commit 3
            @  Commit 2
            o  Commit 1
            +  Initial commit
        """)

        # Create a new commit forked off of $target
        stack = jj.checkable_stack()
        target = stack[0]
        with jj.with_new(target):
            jj.describe(jj.ChangeId("@"), "New commit")
            assert jj.diagram() == dedent("""
                @  New commit
                | o  Commit 3
                | o  Commit 2
                |/
                o  Commit 1
                +  Initial commit
            """)

        # Return to original commit, with new commit forked
        assert jj.diagram() == dedent("""
            o  Commit 3
            @  Commit 2
            | o  New commit
            |/
            o  Commit 1
            +  Initial commit
        """)
