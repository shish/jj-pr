"""
This is a port of the PHP ArcanistDiffParserTestCase to Python,
focusing only on test data for *.udiff and *.gitdiff files.
"""

from pathlib import Path

import pytest

from . import arcdiff
from .arcdiff import ChangeType, FileType


EXPECTED_GIT_COMMIT_MESSAGE = (
    "\n"
    "Deprecating UIActionButton (Part 1)\n"
    "\n"
    "Summary: Replaces calls to UIActionButton with <ui:button>.  I tested most\n"
    "         of these calls, but there were some that I didn't know how to\n"
    "         reach, so if you are one of the owners of this code, please test\n"
    "         your feature in my sandbox: www.ngao.devrs013.facebook.com\n"
    "\n"
    "         @brosenthal, I removed some logic that was setting a disabled state\n"
    "         on a UIActionButton, which is actually a no-op.\n"
    "\n"
    "Reviewed By: brosenthal\n"
    "\n"
    "Other Commenters: sparker, egiovanola\n"
    "\n"
    "Test Plan: www.ngao.devrs013.facebook.com\n"
    "\n"
    "           Explicitly tested:\n"
    "           * ads creation flow (add keyword)\n"
    "           * ads manager (conversion tracking)\n"
    "           * help center (create a discussion)\n"
    "           * new user wizard (next step button)\n"
    "\n"
    "Revert: OK\n"
    "\n"
    "DiffCamp Revision: 94064\n"
    "\n"
    "git-svn-id: svn+ssh://tubbs/svnroot/tfb/trunk/www@223593 2c7ba8d8"
)


class TestArcanistDiffParser:
    @pytest.fixture
    def diff_test_dir(self) -> Path:
        return Path(__file__).parent / "arcdiff_test"

    def parse_diff(self, diff_file: Path) -> list:
        contents = diff_file.read_text()
        return arcdiff.parse_diff(contents)

    def parse_diff_text(self, diff_text: str) -> list:
        return arcdiff.parse_diff(diff_text)

    def run_single_rename(
        self,
        diffline: str,
        from_path: str,
        to_path: str,
        old_path: str,
        new_path: str,
    ):
        diff_text = (
            f"diff --git {diffline}\n"
            "similarity index 95%\n"
            f"rename from {from_path}\n"
            f"rename to {to_path}\n"
        )

        changes = self.parse_diff_text(diff_text)

        assert changes is not None, f"Parsed:\n{diff_text}"
        expected_count = 1 if old_path == new_path else 2
        assert len(changes) == expected_count, f"Parsed one change:\n{diff_text}"

        change = changes[0]
        assert (change.old_path, change.current_path) == (
            old_path,
            new_path,
        ), f"Split: {diffline}"

    def test_to_conduit(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-multi-hunk.udiff"
        changes = arcdiff.changes_to_conduit(self.parse_diff(diff_file))
        c0 = changes[0]
        assert c0["fileType"] == 1

    def test_basic_binary_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-binary.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.file_type == FileType.BINARY

    def test_basic_missing_both_newlines_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-both-newlines.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is True
        assert hunk.is_missing_new_newline is True

    def test_basic_missing_both_newlines_plus_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-both-newlines-plus.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is True
        assert hunk.is_missing_new_newline is True

    def test_basic_missing_new_newline_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-new-newline.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is False
        assert hunk.is_missing_new_newline is True

    def test_basic_missing_new_newline_plus_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-new-newline-plus.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is False
        assert hunk.is_missing_new_newline is True

    def test_basic_missing_old_newline_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-old-newline.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is True
        assert hunk.is_missing_new_newline is False

    def test_basic_missing_old_newline_plus_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-missing-old-newline-plus.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 1

        hunk = hunks[0]
        assert hunk.is_missing_old_newline is True
        assert hunk.is_missing_new_newline is False

    def test_basic_multi_hunk_udiff(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "basic-multi-hunk.udiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        hunks = change.hunks
        assert len(hunks) == 4
        assert change.current_path == "right"
        assert change.old_path == "left"

    def test_git_delete_file(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-delete-file.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.DELETE
        assert change.current_path == "scripts/intern/test/testfile2"
        assert len(change.hunks) == 1

    def test_git_binary_change(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-binary-change.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.file_type == FileType.BINARY
        assert len(change.hunks) == 0

    def test_git_filemode_change(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-filemode-change.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.hunks) == 1
        assert change.old_properties == {"unix:filemode": "100644"}
        assert change.new_properties == {"unix:filemode": "100755"}

    def test_git_filemode_change_only(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-filemode-change-only.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        change = changes[0]
        assert len(change.hunks) == 0
        assert change.old_properties == {"unix:filemode": "100644"}
        assert change.new_properties == {"unix:filemode": "100755"}

    def test_git_ignore_whitespace_only(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-ignore-whitespace-only.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert len(change.hunks) == 0
        assert change.old_path == "scripts/intern/test/testfile2"
        assert change.current_path == "scripts/intern/test/testfile2"

        change = changes[1]
        assert len(change.hunks) == 1
        assert change.old_path == "scripts/intern/test/testfile3"
        assert change.current_path == "scripts/intern/test/testfile3"

    def test_git_move(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-move.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.MOVE_HERE

        target = change

        change = changes[1]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.MOVE_AWAY

        assert change.current_path == target.old_path
        assert target.current_path in change.away_paths

    def test_git_move_edit(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-move-edit.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert len(change.hunks) == 1
        assert change.type == ChangeType.MOVE_HERE

        change = changes[1]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.MOVE_AWAY

    def test_git_move_plus(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-move-plus.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 3

        change = changes[0]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.MOVE_HERE

        target = change

        change = changes[1]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.MOVE_AWAY

        assert change.current_path == target.old_path
        assert target.current_path in change.away_paths

    def test_git_merge_header(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-merge-header.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.MESSAGE
        assert change.commit_hash == "501f6d519703458471dbea6284ec5f49d1408598"

    def test_git_new_file(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-new-file.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.ADD

    def test_git_copy(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-copy.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.COPY_HERE
        assert change.current_path == "flib/intern/widgets/ui/UIWidgetRSSBox.php"

        change = changes[1]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.COPY_AWAY
        assert change.current_path == "lib/display/intern/ui/widget/UIWidgetRSSBox.php"

    def test_git_copy_plus(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-copy-plus.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert len(change.hunks) == 3
        assert change.type == ChangeType.COPY_HERE
        assert change.current_path == "flib/intern/widgets/ui/UIWidgetGraphConnect.php"

        change = changes[1]
        assert len(change.hunks) == 0
        assert change.type == ChangeType.COPY_AWAY
        assert (
            change.current_path == "lib/display/intern/ui/widget/UIWidgetLunchtime.php"
        )

    def test_git_empty_files(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-empty-files.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        for change in changes:
            assert len(change.hunks) == 0

    def test_git_mnemonicprefix(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-mnemonicprefix.gitdiff"
        changes = self.parse_diff(diff_file)

        # Diffs created with git diff.mnemonicprefix=true.
        assert len(changes) == 1
        assert len(changes[0].hunks) == 1

    def test_git_commit(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-commit.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.MESSAGE
        assert change.commit_hash == "76e2f1339c298c748aa0b52030799ed202a6537b"
        assert change.metadata["message"] == EXPECTED_GIT_COMMIT_MESSAGE

    def test_git_commit_logdecorate(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-commit-logdecorate.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.MESSAGE
        assert change.commit_hash == "76e2f1339c298c748aa0b52030799ed202a6537b"
        assert change.metadata["message"] == EXPECTED_GIT_COMMIT_MESSAGE

    def test_git_binary(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-binary.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.CHANGE
        assert change.file_type == FileType.BINARY

    def test_git_odd_filename(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-odd-filename.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2
        change = changes[0]
        assert change.old_path == "old/∆.jpg"
        assert change.current_path == "new/∆.jpg"

    def test_git_replace_symlink(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-replace-symlink.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == ChangeType.CHANGE

    def test_git_format_patch(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-format-patch.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 2

        change = changes[0]
        assert change.type == ChangeType.MESSAGE
        assert change.metadata["message"] == "WIP"

        change = changes[1]
        assert change.type == ChangeType.CHANGE

    def test_custom_prefixes(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "custom-prefixes.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.current_path == "file"

    def test_custom_prefixes_edit(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "custom-prefixes-edit.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.current_path == "file"

    def test_suppress_blank_empty(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "suppress-blank-empty.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1

    def test_git_remove_spaces(self, diff_test_dir: Path):
        diff_file = diff_test_dir / "git-remove-spaces.gitdiff"
        changes = self.parse_diff(diff_file)

        assert len(changes) == 1
        change = changes[0]
        assert change.old_path == "file with spaces.txt"

    def test_git_common_filename_extraction(self):
        tests = [
            ("a/filename.c b/filename.c", "filename.c"),
            ("a/filename.c b/filename.c\n", "filename.c"),
            ("a/filename.c b/filename.c\r\n", "filename.c"),
            ("filename.c filename.c", "filename.c"),
            ("1/filename.c 2/filename.c", "filename.c"),
            (r'"a/\"quotes\"" "b/\"quotes\""', '"quotes"'),
            (
                r'"a/\"quotes and spaces\"" "b/\"quotes and spaces\""',
                '"quotes and spaces"',
            ),
            (r'"a/\342\230\203" "b/\342\230\203"', "☃"),
            ("a/Core Data/filename.c b/Core Data/filename.c", "Core Data/filename.c"),
            (
                "some file with spaces.c some file with spaces.c",
                "some file with spaces.c",
            ),
            ('"foo bar.c" foo bar.c', "foo bar.c"),
            ('"a/foo bar.c" b/foo bar.c', "foo bar.c"),
            ("src/file dst/file", "file"),
            # Renames are handled by explicit `rename from ...` lines.
            ("a/foo.c b/bar.c", None),
            ("a/foo bar.c b/baz troz.c", None),
            ('"a/foo bar.c" b/baz troz.c', None),
            ('a/foo bar.c "b/baz troz.c"', None),
            ('"a/foo bar.c" "b/baz troz.c"', None),
            (
                "filename file with spaces.c filename file with spaces.c",
                "filename file with spaces.c",
            ),
        ]

        for input_text, expected in tests:
            result = arcdiff.extract_git_common_filename(input_text)
            assert result == expected, f"Split: {input_text}"

    def test_git_renames(self):
        self.run_single_rename(
            "a/old.c b/new.c",
            "old.c",
            "new.c",
            "old.c",
            "new.c",
        )
        self.run_single_rename(
            "old.c new.c",
            "old.c",
            "new.c",
            "old.c",
            "new.c",
        )
        self.run_single_rename(
            "1/old.c 2/new.c",
            "old.c",
            "new.c",
            "old.c",
            "new.c",
        )
        self.run_single_rename(
            "from/file.c to/file.c",
            "from/file.c",
            "to/file.c",
            "from/file.c",
            "to/file.c",
        )
        self.run_single_rename(
            r'"a/\"quotes1\"" "b/\"quotes2\""',
            r'"\"quotes1\""',
            r'"\"quotes2\""',
            '"quotes1"',
            '"quotes2"',
        )
        self.run_single_rename(
            r'"a/\"quotes spaces1\"" "b/\"quotes spaces2\""',
            r'"\"quotes spaces1\""',
            r'"\"quotes spaces2\""',
            '"quotes spaces1"',
            '"quotes spaces2"',
        )
        self.run_single_rename(
            r'"a/\342\230\2031" "b/\342\230\2032"',
            r'"\342\230\2031"',
            r'"\342\230\2032"',
            "☃1",
            "☃2",
        )
        self.run_single_rename(
            "a/Core Data/old.c b/Core Data/new.c",
            "Core Data/old.c",
            "Core Data/new.c",
            "Core Data/old.c",
            "Core Data/new.c",
        )
        self.run_single_rename(
            "file with spaces.c file with spaces.c",
            "file with spaces.c",
            "file with spaces.c",
            "file with spaces.c",
            "file with spaces.c",
        )
        self.run_single_rename(
            'a/non-quoted filename.c "b/quoted filename.c"',
            "non-quoted filename.c",
            '"quoted filename.c"',
            "non-quoted filename.c",
            "quoted filename.c",
        )
        self.run_single_rename(
            'non-quoted filename.c "quoted filename.c"',
            "non-quoted filename.c",
            '"quoted filename.c"',
            "non-quoted filename.c",
            "quoted filename.c",
        )
        self.run_single_rename(
            '"a/quoted filename.c" b/non quoted filename.c',
            '"quoted filename.c"',
            "non quoted filename.c",
            "quoted filename.c",
            "non quoted filename.c",
        )
        self.run_single_rename(
            '"quoted filename.c" non-quoted filename.c',
            '"quoted filename.c"',
            "non-quoted filename.c",
            "quoted filename.c",
            "non-quoted filename.c",
        )
        self.run_single_rename(
            "old file with spaces.c new file with spaces.c",
            "old file with spaces.c",
            "new file with spaces.c",
            "old file with spaces.c",
            "new file with spaces.c",
        )
        self.run_single_rename(
            "old file old file",
            "old file old",
            "file",
            "old file old",
            "file",
        )
