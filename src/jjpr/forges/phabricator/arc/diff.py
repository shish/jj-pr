"""
Arcanist diff parser - parses unified and git diffs.

This is a Python port of (the git and unified-diff subset of)
`ArcanistDiffParser.php`. Mercurial, Subversion, and RCS support from the
original PHP parser have been intentionally omitted, since jj-pr only needs
to understand `git diff` / `git show` / unified diff output.

The port tries to stay close to the structure and behavior of the PHP
original so that it can be cross-checked against
`ArcanistDiffParserTestCase.php` (see `arcdiff_test.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, NoReturn


class DiffParseError(Exception):
    """Raised when a diff cannot be parsed."""


class ChangeType(IntEnum):
    ADD = 1
    CHANGE = 2
    DELETE = 3
    MOVE_AWAY = 4
    COPY_AWAY = 5
    MOVE_HERE = 6
    COPY_HERE = 7
    MULTICOPY = 8
    MESSAGE = 9


class FileType(IntEnum):
    TEXT = 1
    BINARY = 3


@dataclass
class Hunk:
    """Represents a hunk within a diff."""

    old_offset: int = 0
    old_length: int = 0
    new_offset: int = 0
    new_length: int = 0
    add_lines: int = 0
    del_lines: int = 0
    is_missing_old_newline: bool = False
    is_missing_new_newline: bool = False
    corpus: str = ""

    def to_conduit(self) -> dict[str, Any]:
        return {
            "oldOffset": self.old_offset,
            "oldLength": self.old_length,
            "newOffset": self.new_offset,
            "newLength": self.new_length,
            "addLines": self.add_lines,
            "delLines": self.del_lines,
            "isMissingOldNewline": self.is_missing_old_newline,
            "isMissingNewNewline": self.is_missing_new_newline,
            "corpus": self.corpus,
        }


@dataclass
class Change:
    """Represents a change within a diff."""

    type: ChangeType = ChangeType.CHANGE
    file_type: FileType = FileType.TEXT
    old_path: str = ""
    current_path: str = ""
    hunks: list[Hunk] = field(default_factory=list)
    old_properties: dict[str, str] = field(default_factory=dict)
    new_properties: dict[str, str] = field(default_factory=dict)
    commit_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    away_paths: list[str] = field(default_factory=list)

    def to_conduit(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "oldPath": self.old_path or None,
            "currentPath": self.current_path or None,
            "awayPaths": self.away_paths,
            "oldProperties": self.old_properties,
            "newProperties": self.new_properties,
            "type": int(self.type),
            "fileType": int(self.file_type),
            "commitHash": self.commit_hash or None,
            "hunks": [hunk.to_conduit() for hunk in self.hunks],
        }


def unescape_filename(name: str) -> str:
    """
    Unescape escaped filenames, e.g. from "git diff".

    Filenames containing unusual characters are quoted and C-style escaped
    by git (e.g. `"a/\\342\\230\\203"`). This mirrors PHP's `stripcslashes()`
    applied to the quoted content, then decodes the resulting bytes as
    UTF-8, matching `ArcanistDiffParser::unescapeFilename()`.
    """
    if re.match(r'^".+"$', name, re.DOTALL):
        return _stripcslashes(name[1:-1])
    return name


def _stripcslashes(text: str) -> str:
    out = bytearray()
    i = 0
    n = len(text)
    simple_escapes = {
        "n": b"\n",
        "t": b"\t",
        "r": b"\r",
        "a": b"\x07",
        "v": b"\x0b",
        "b": b"\x08",
        "f": b"\x0c",
    }
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in "01234567":
                j = i + 1
                digits = ""
                while j < n and len(digits) < 3 and text[j] in "01234567":
                    digits += text[j]
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
                continue
            if nxt == "x":
                j = i + 2
                digits = ""
                while j < n and len(digits) < 2 and text[j] in "0123456789abcdefABCDEF":
                    digits += text[j]
                    j += 1
                if digits:
                    out.append(int(digits, 16) & 0xFF)
                    i = j
                else:
                    out.extend(b"x")
                    i += 2
                continue
            if nxt in simple_escapes:
                out.extend(simple_escapes[nxt])
            else:
                out.extend(nxt.encode("utf-8"))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    try:
        return bytes(out).decode("utf-8")
    except UnicodeDecodeError:
        return bytes(out).decode("latin-1")


def extract_git_common_filename(paths: str) -> str | None:
    """
    Extracts the common filename from two strings with differing path
    prefixes as found after `diff --git`. These strings may be quoted; if
    so, the filename is returned unescaped. The prefixes default to "a/"
    and "b/", but may be any string -- or may be entirely absent. This
    function may return `None` if the hunk represents a file move or copy,
    and with pathological renames may return an incorrect value. Such cases
    are expected to be recovered by later rename-detection codepaths.
    """
    paths = paths.rstrip("\r\n")

    prefix = r"(?:[^/]+/)?"
    pattern = (
        r'^(?P<old>(?P<oldq>"?)' + prefix + r"(?P<common>.+)(?P=oldq))"
        r" "
        r'(?P<new>(?P<newq>"?)' + prefix + r"(?P=common)(?P=newq))$"
    )

    match = re.match(pattern, paths)
    if not match:
        # A rename of some form; return None for now, and let the
        # "rename from" / "rename to" lines fix it up.
        return None

    new = match.group("newq") + match.group("common") + match.group("newq")
    return unescape_filename(new)


# --- Top-level diff header patterns (git / unified-diff subset only) ---

_HEADER_PATTERNS = [
    re.compile(r"^(?P<type>commit) (?P<hash>[a-f0-9]+)(?: \(.*\))?$"),
    re.compile(r"^(?P<type>diff --git) (?P<oldnew>.*)$"),
    re.compile(r"^(?P<type>---) (?P<old>.+)\s+\d{4}-\d{2}-\d{2}.*$"),
    re.compile(
        r"^(?P<binary>Binary files|Files) (?P<old>.+)\s+\d{4}-\d{2}-\d{2} and "
        r"(?P<new>.+)\s+\d{4}-\d{2}-\d{2} differ.*$"
    ),
]

_GIT_INDEX_PATTERNS = [
    re.compile(r"^(?P<new>new) file mode (?P<newmode>\d+)"),
    re.compile(r"^(?P<deleted>deleted) file mode (?P<oldmode>\d+)"),
    re.compile(r"^old mode (?P<oldmode>\d+)"),
    re.compile(r"^new mode (?P<newmode>\d+)"),
    re.compile(r"^similarity index "),
    re.compile(r"^rename from (?P<old>.*)"),
    re.compile(r"^(?P<move>rename) to (?P<cur>.*)"),
    re.compile(r"^copy from (?P<old>.*)"),
    re.compile(r"^(?P<copy>copy) to (?P<cur>.*)"),
]

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*?)?$")


class _Parser:
    """Internal line-cursor-based diff parser (git + unified diff subset)."""

    def __init__(self) -> None:
        self.text: list[str] = []
        self.line = 0
        self.is_git: bool | None = None
        self._changes: list[Change] = []
        self._by_path: dict[str, Change] = {}

    # -- line cursor helpers -------------------------------------------------

    def did_start_parse(self, diff: str) -> None:
        text = diff.lstrip()

        ansi = r"\x1B\[[\d;]*m"
        if re.search(r"(?m)^" + ansi, text):
            text = re.sub(ansi, "", text)

        self.text = text.splitlines(keepends=True)
        self.line = 0

    def did_finish_parse(self) -> None:
        self.text = []

    def get_line(self) -> str | None:
        if 0 <= self.line < len(self.text):
            return self.text[self.line]
        return None

    def get_line_trimmed(self) -> str | None:
        line = self.get_line()
        if line is not None:
            line = line.strip("\r\n")
        return line

    def next_line(self) -> str | None:
        self.line += 1
        return self.get_line()

    def next_line_trimmed(self) -> str | None:
        line = self.next_line()
        if line is not None:
            line = line.strip("\r\n")
        return line

    def next_nonempty_line(self) -> str | None:
        while True:
            line = self.next_line()
            if line is None or line.strip() != "":
                break
        return self.get_line()

    def did_fail_parse(self, message: str) -> NoReturn:
        raise DiffParseError(message)

    # -- change bookkeeping ---------------------------------------------------

    def build_change(self, path: str | None) -> Change:
        if path is not None and path in self._by_path:
            return self._by_path[path]

        change = Change()
        if path is not None:
            change.current_path = path
            self._by_path[path] = change
        self._changes.append(change)
        return change

    def set_is_git(self, is_git: bool) -> None:
        if self.is_git is not None and self.is_git != is_git:
            raise DiffParseError("Git status has changed!")
        self.is_git = is_git

    def mark_binary(self, change: Change) -> None:
        change.file_type = FileType.BINARY

    # -- top-level parse ------------------------------------------------------

    def parse_diff(self, diff: str) -> list[Change]:
        if not diff.strip():
            raise DiffParseError("Can't parse an empty diff!")

        message = None
        if re.search(r"(?ms)^---$.*^-- ?[\s\d.]+\Z", diff):
            message, diff = self._strip_git_format_patch(diff)

        self.did_start_parse(diff)

        line = self.get_line_trimmed()
        while line is not None and line.startswith("#"):
            line = self.next_line()

        if message is not None and len(message):
            change = self.build_change(None)
            change.type = ChangeType.MESSAGE
            change.metadata["message"] = message

        while True:
            line = self.get_line_trimmed()
            match = self._try_match_header(line)

            if match is None:
                self.did_fail_parse(
                    "Expected a hunk header, like 'commit <hash>' (git show), "
                    "'diff --git ...' (git diff), or '--- filename' "
                    "(unified diff)."
                )

            gd = match.groupdict()

            if gd.get("type") == "diff --git":
                filename = extract_git_common_filename(gd["oldnew"])
                if filename is not None:
                    gd["old"] = filename
                    gd["cur"] = filename

            change = self.build_change(gd.get("cur"))

            if gd.get("old"):
                change.old_path = gd["old"]

            if gd.get("hash"):
                change.commit_hash = gd["hash"]

            if gd.get("binary"):
                change.file_type = FileType.BINARY
                line = self.next_nonempty_line()
                if line is None:
                    break
                continue

            line = self.next_line()

            diff_type = gd["type"]
            if diff_type == "diff --git":
                self.set_is_git(True)
                self.parse_index_hunk(change)
            elif diff_type == "commit":
                self.set_is_git(True)
                self.parse_commit_message(change)
            elif diff_type == "---":
                m = re.match(r"^\+\+\+ (.*)\s+\d{4}-\d{2}-\d{2}.*$", line or "")
                if not m:
                    self.did_fail_parse("Expected '+++ filename' in unified diff.")
                change.current_path = m.group(1)
                self.next_line()
                self.parse_changeset(change)
            else:
                self.did_fail_parse("Unknown diff type.")

            if self.get_line() is None:
                break

        self.did_finish_parse()
        return self._changes

    def _try_match_header(self, line: str | None):
        if line is None:
            return None
        for pattern in _HEADER_PATTERNS:
            match = pattern.match(line)
            if match:
                return match
        return None

    # -- commit messages --------------------------------------------------

    def parse_commit_message(self, change: Change) -> None:
        change.type = ChangeType.MESSAGE
        message: list[str] = []

        line = self.get_line()
        if line is not None and re.match(r"^Merge: ", line):
            self.next_line()

        line = self.get_line()
        if line is None or not re.match(r"^Author: ", line):
            self.did_fail_parse("Expected 'Author:'.")

        line = self.next_line()
        if line is None or not re.match(r"^Date: ", line):
            self.did_fail_parse("Expected 'Date:'.")

        while True:
            line = self.next_line_trimmed()
            if line is None:
                break
            if len(line) and line[0] != " ":
                break
            message.append(re.sub(r"^    ", "", self.get_line() or ""))

        text = "".join(message).rstrip("\r\n")
        change.metadata["message"] = text

    # -- git index hunks (mode/rename/copy metadata + binary detection) ---

    def parse_index_hunk(self, change: Change) -> None:
        is_git = bool(self.is_git)
        move_source: Change | None = None

        line = self.get_line()

        if is_git:
            while True:
                match = None
                if line is not None:
                    for pattern in _GIT_INDEX_PATTERNS:
                        match = pattern.match(line)
                        if match:
                            break
                    else:
                        match = None

                if match is None:
                    if line is None or re.match(r"^(diff --git|commit) ", line):
                        return
                    break

                gd = match.groupdict()

                if gd.get("oldmode"):
                    change.old_properties["unix:filemode"] = gd["oldmode"]
                if gd.get("newmode"):
                    change.new_properties["unix:filemode"] = gd["newmode"]

                if gd.get("deleted"):
                    change.type = ChangeType.DELETE

                if gd.get("new"):
                    # If you replace a symlink with a normal file, git renders
                    # the change as a "delete" of the symlink plus an "add" of
                    # the new file. We prefer to represent this as a change.
                    if change.type == ChangeType.DELETE:
                        change.type = ChangeType.CHANGE
                    else:
                        change.type = ChangeType.ADD

                if gd.get("old"):
                    change.old_path = unescape_filename(gd["old"])

                if gd.get("cur"):
                    change.current_path = unescape_filename(gd["cur"])

                if gd.get("copy"):
                    change.type = ChangeType.COPY_HERE
                    old = self.build_change(change.old_path)
                    if old.type == ChangeType.MOVE_AWAY:
                        old.type = ChangeType.MULTICOPY
                    else:
                        old.type = ChangeType.COPY_AWAY
                    old.away_paths.append(change.current_path)

                if gd.get("move"):
                    change.type = ChangeType.MOVE_HERE
                    old = self.build_change(change.old_path)
                    if old.type == ChangeType.MULTICOPY:
                        pass
                    elif (
                        old.type == ChangeType.MOVE_AWAY
                        or old.type == ChangeType.COPY_AWAY
                    ):
                        old.type = ChangeType.MULTICOPY
                    else:
                        old.type = ChangeType.MOVE_AWAY
                    move_source = old
                    old.away_paths.append(change.current_path)

                line = self.next_nonempty_line()

        del move_source  # only meaningful for synthetic-hunk loading, unused

        line = self.get_line()

        if is_git and line is not None and re.match(r"^index .*$", line):
            line = self.next_nonempty_line()

        if line is None or re.match(
            r"^(Index:|Property changes on:|diff --git|commit) ", line
        ):
            return

        stripped = line.rstrip("\r\n")

        if re.match(r"^Cannot display: file marked as a binary type\.$", stripped):
            self.next_line()
            self.next_nonempty_line()
            self.mark_binary(change)
            return

        if re.match(r"^(Binary files|Files) .* and .* differ$", stripped):
            self.next_nonempty_line()
            self.mark_binary(change)
            return

        if re.match(r"^Binary file .* has changed$", stripped):
            self.next_nonempty_line()
            self.mark_binary(change)
            return

        if re.match(r"^GIT binary patch$", stripped):
            self.next_line()
            self.parse_git_binary_patch()
            line = self.get_line()
            if line is not None and re.match(r"^literal", line):
                self.parse_git_binary_patch()
            self.mark_binary(change)
            return

        if is_git and re.match(r"^diff --git .*$", line):
            self.next_line()
            return

        old_file = self.parse_hunk_target()
        self.parse_hunk_target()  # new_file target; unused outside RCS support
        change.old_path = old_file

        self.parse_changeset(change)

    def parse_git_binary_patch(self) -> None:
        line = self.get_line()
        if line is None or not re.match(r"^literal ", line):
            self.did_fail_parse("Expected 'literal NNNN' to start git binary patch.")
        while True:
            line = self.next_line_trimmed()
            if line == "" or line is None:
                self.next_nonempty_line()
                return
            if not re.match(r"^[a-zA-Z]", line):
                self.did_fail_parse("Expected base85 line length character (a-zA-Z).")

    def parse_hunk_target(self) -> str:
        line = self.get_line()

        if self.is_git:
            # When filenames contain spaces, Git terminates this line with a
            # tab. Normally, the tab is not present. If there's a tab, ignore
            # it.
            remainder = r"(?:\t.*)?"
        else:
            remainder = r"(?:\s*\(.*\))?"

        match = re.match(
            r"^[-+]{3} (?:[ab]/)?(?P<path>.*?)" + remainder + r"$", line or ""
        )
        if not match:
            self.did_fail_parse(
                "Expected hunk target '+++ path/to/file.ext (revision N)'."
            )

        self.next_line()
        return match.group("path")

    # -- hunk bodies --------------------------------------------------------

    def parse_changeset(self, change: Change) -> None:
        # If a diff includes two sets of changes to the same file, let the
        # second one win (see T5555 in the original Arcanist parser).
        change.hunks = []

        while True:
            hunk = Hunk()
            line = self.get_line_trimmed()
            match = _HUNK_HEADER_RE.match(line or "")

            if not match:
                if line == "":
                    self.did_fail_parse("Confused by empty line")
                self.did_fail_parse("Expected hunk header '@@ -NN,NN +NN,NN @@'.")

            hunk.old_offset = int(match.group(1))
            hunk.new_offset = int(match.group(3))
            old_len = int(match.group(2)) if match.group(2) else 1
            new_len = int(match.group(4)) if match.group(4) else 1
            hunk.old_length = old_len
            hunk.new_length = new_len

            add = 0
            del_lines = 0
            real: list[str] = []
            hit_next_hunk = False
            raw_line: str | None = None

            while True:
                raw_line = self.next_line()
                if raw_line is None:
                    break

                stripped = raw_line.rstrip("\r\n")
                char = stripped[0] if stripped else " "

                if char == "\\":
                    if "No newline at end of file" not in raw_line:
                        self.did_fail_parse("Expected '\\ No newline at end of file'.")
                    if new_len:
                        real.append(raw_line)
                        hunk.is_missing_old_newline = True
                    else:
                        real.append(raw_line)
                        hunk.is_missing_new_newline = True
                    if not new_len:
                        break
                elif char == "+":
                    add += 1
                    new_len -= 1
                    real.append(raw_line)
                elif char == "-":
                    if not old_len:
                        # We've hit "---" from a new file; don't advance the
                        # line cursor further than we already have.
                        hit_next_hunk = True
                        break
                    del_lines += 1
                    old_len -= 1
                    real.append(raw_line)
                elif char == " ":
                    if not old_len and not new_len:
                        break
                    old_len -= 1
                    new_len -= 1
                    real.append(raw_line)
                else:
                    hit_next_hunk = True
                    break

            if old_len or new_len:
                self.did_fail_parse("Found the wrong number of hunk lines.")

            hunk.corpus = "".join(real)
            hunk.add_lines = add
            hunk.del_lines = del_lines
            change.hunks.append(hunk)

            if not hit_next_hunk:
                raw_line = self.next_nonempty_line()

            if raw_line is None or not raw_line.startswith("@@ "):
                break

    # -- git-format-patch stripping -----------------------------------------

    def _strip_git_format_patch(self, diff: str) -> tuple[str, str]:
        head, tail = re.split(r"(?m)^---$", diff, maxsplit=1)
        mail_headers, mail_body = head.split("\n\n", 1)
        body, _foot = re.split(r"(?m)^-- ?$", tail, maxsplit=1)
        _stat, diff_text = body.split("\n\n", 1)

        match = re.search(r"(?mi)^Subject: (?:\[PATCH\] )?(.*)$", mail_headers)
        if match:
            mail_body = match.group(1) + "\n\n" + mail_body
            mail_body = mail_body.rstrip()

        return mail_body, diff_text


def parse_diff(diff: str) -> list[Change]:
    """
    Parse a diff string and return a list of Change objects.
    """
    return _Parser().parse_diff(diff)


def changes_to_conduit(changes: list[Change]) -> list[dict[str, Any]]:
    """
    Convert a list of `Change` objects (as returned by `parse_diff`) into the
    list-of-dicts shape expected by the `changes` parameter of the
    `differential.creatediff` conduit method (i.e. what
    `ArcanistDiffChange::newFromDictionary()` expects).
    """
    return [change.to_conduit() for change in changes]
