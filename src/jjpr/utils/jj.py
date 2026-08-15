import json
import logging
import re
import shlex
import subprocess
import typing as t
from contextlib import contextmanager

from . import cr, exec, text

#######################################################################
# Utilities

log = logging.getLogger(__name__)

# Type aliases
ChangeId = t.NewType("ChangeId", str)
_RevSet = t.NewType("_RevSet", str)  # Specifically and only a revset
RevSet = t.LiteralString | _RevSet | ChangeId  # Anything which counts as a revset


class JjError(Exception):
    pass


@t.overload
def run(*args: str, cap: t.Literal[True]) -> str: ...


@t.overload
def run(*args: str, cap: t.Literal[False]) -> None: ...


@t.overload
def run(*args: str) -> str: ...


def run(*args: str, cap: bool = True) -> str | None:
    try:
        return exec.run("jj", *args, cap=cap)  # type: ignore
    except subprocess.CalledProcessError as e:
        e2 = JjError(f"Failed to run {shlex.join(['jj', *args])!r} ({e.returncode})")
        if cap:
            e2.add_note(f"stdout: {text.remove_ansi(e.stdout.strip())}")
            e2.add_note(f"stderr: {text.remove_ansi(e.stderr.strip())}")
        raise e2 from e


#######################################################################
# Direct mappings to jj commands


def bookmark_advance(name: str, to: RevSet) -> None:
    run("bookmark", "advance", name, "--to", to, cap=False)


def bookmark_create(name: str, r: RevSet) -> None:
    run("bookmark", "create", name, "-r", r, cap=False)


def bookmark_track(name: str, remote: str) -> None:
    run("bookmark", "track", name, "--remote", remote, cap=False)


def commit(m: str) -> None:
    run("commit", "-m", m, cap=False)


def config_get(key: str) -> str | None:
    try:
        return run("--ignore-working-copy", "config", "get", key, cap=True)
    except JjError:
        return None


def describe(r: ChangeId, m: str) -> None:
    run("describe", "-r", r, "-m", m)


def edit(r: ChangeId) -> None:
    run("edit", "-r", r, cap=False)


def gerrit_upload(
    remote: str,
    r: str,
    wip: bool = False,
    message: str | None = None,
    remote_branch: str | None = None,
) -> None:
    args = ["gerrit", "upload", "--remote", remote, "-r", r]
    if wip:
        args.append("--wip")
    if message:
        args.extend(["--message", message])
    if remote_branch:
        args.extend(["--remote-branch", remote_branch])
    run(*args, cap=False)


def git_fetch(remote: str | None = None, all_remotes: bool = False) -> None:
    cmd = ["git", "fetch"]
    if remote:
        cmd.append("--remote")
        cmd.append(remote)
    if all_remotes:
        cmd.append("--all-remotes")
    run(*cmd, cap=False)


def git_push(remote: str, bookmark: str) -> None:
    run("git", "push", "--remote", remote, "--bookmark", bookmark, cap=False)


def new(r: RevSet) -> None:
    run("new", "-r", r, cap=False)


def rebase(d: RevSet, r: RevSet | None = None, s: RevSet | None = None) -> None:
    cmd = ["rebase", "--skip-emptied", "-d", d]
    if r:
        cmd.extend(["-r", r])
    if s:
        cmd.extend(["-s", s])
    run(*cmd, cap=False)


def root() -> str:
    return run("root", cap=True)


#######################################################################
# change_info and wrappers


def change_info(change_id: ChangeId, t: str) -> str:
    return run("--ignore-working-copy", "log", "-r", change_id, "--no-graph", "-T", t)


def parents_of(change_id: ChangeId) -> set[ChangeId]:
    """
    List all parent change IDs for a given change ID
    """
    output = change_info(change_id, 'parents.map(|p| p.change_id()).join("\\n")')
    return {ChangeId(p) for p in output.split("\n") if p}


def files_in(change_id: ChangeId) -> set[str]:
    """
    List all files changed in a given change ID
    """
    output = change_info(change_id, 'self.diff().files().map(|f| f.path()).join("\\n")')
    return {f for f in output.split("\n") if f}


def description_of(change_id: ChangeId) -> str:
    """
    Get the description of a commit
    """
    output = change_info(change_id, "self.description()")
    return output.strip()


def branches_pointing_to(change_id: ChangeId, prefix: str = "") -> set[str]:
    """
    Find all branches pointing to a given change ID, optionally filtering by prefix
    """
    output = change_info(change_id, 'self.bookmarks().map(|b| b.name()).join("\\n")')
    return {b for b in output.split("\n") if b and b.startswith(prefix)}


def commit_id(change_id: ChangeId) -> str:
    """
    Get the commit ID for a given change ID
    """
    return change_info(change_id, "self.commit_id()")


#######################################################################
# Extra helpers


@t.overload
def revset(r: str) -> _RevSet: ...


@t.overload
def revset(r: None) -> None: ...


def revset(r: str | None) -> _RevSet | None:
    """
    Convert a revset-like string into a _RevSet type, which is used to indicate
    that the string is specifically a revset and not just any string.
    """
    if r is None:
        return None
    return _RevSet(r)


def change_ids(r: RevSet) -> list[ChangeId]:
    """
    Return a list of change IDs for the given revset, in reverse order (oldest first).
    """
    lines = run(
        "log",
        "-r",
        r,
        "--no-graph",
        "--reversed",
        "-T",
        'self.change_id() ++ "\\n"',
        cap=True,
    ).split("\n")
    return [ChangeId(line) for line in lines if line]


def change_id(revset: RevSet) -> ChangeId:
    """
    Return the change ID for the given revset (eg "@" or "trunk()");
    raise an error if it resolves to zero or multiple change IDs.
    """
    cs = change_ids(revset)
    if len(cs) == 0:
        raise ValueError(f"Revset {revset!r} did not resolve to any change IDs")
    if len(cs) != 1:
        raise ValueError(f"Revset {revset!r} resolved to multiple change IDs: {cs}")
    return cs[0]


def closest_work() -> ChangeId:
    """
    Return the closest non-empty mutable commit

    (Normally either current commit, or parent when current commit is empty)
    """
    return change_id("heads(::@ & mutable() & (~empty() | merges()))")


def pushable_stack() -> list[ChangeId]:
    """
    Find commits in the current stack (mutable commits from the trunk
    up to and including the current commit), with a commit message
    and file changes

    (ie commits which can be meaningfully pushed for review)
    """
    return change_ids(
        'trunk()..heads(::@ & mutable() & ~description(exact:"") & (~empty() | merges()))'
    )


def checkable_stack() -> list[ChangeId]:
    """
    Find commits in the current stack (mutable commits from the trunk
    up to and including the current commit), with file changes

    (ie, commits that can be meaningfully pre-commit checked)
    """
    return change_ids("trunk()..heads(::@ & mutable() & (~empty() | merges()))")


def bookmarks() -> dict[str, dict[str, t.Any]]:
    output = run("bookmark", "list", "-T", 'json(self) ++ "\\n"')
    bs = {}
    for js in [json.loads(b) for b in output.split("\n") if b]:
        name = js["name"]
        if "remote" in js:
            name = f"{name}@{js['remote']}"
        bs[name] = js
    return bs


def log_with_annotations(
    args: list[str],
    template: str,
    get_pr_states: t.Callable[[list[str]], dict[str, cr.CodeReview]],
) -> str:
    """
    - Run `jj log` with a custom template which adds PR IDs into the output
    - Parse a list of PR IDs from the log output
    - Call `get_pr_states` to turn a list of PR IDs into a mapping of {PR ID: State}
    - Replace the PR IDs in the log output with their states
    """
    logdata = run(
        "log",
        "--color",
        "always",
        "--config",
        f"template-aliases.\"format_commit_labels(commit)\"='''\"JJPR:\"++{template}++\":JJPR\"'''",
        *args,
        cap=True,
    )
    # remove empty annotations
    logdata = re.sub("JJPR::JJPR", "", logdata)
    # remove ansi escape codes from inside annotations
    logdata = re.sub(
        r"JJPR:([^\n]*?):JJPR",
        lambda x: f"JJPR:{text.remove_ansi(x.group(1))}:JJPR",
        logdata,
    )
    # extract all PR IDs from the annotations
    pr_ids = re.findall(r"JJPR:([^:]*):JJPR", logdata)

    # build a map of PR IDs to their states using the provided get_pr_states function
    id_to_state = {}
    if pr_ids:
        id_to_state = get_pr_states(pr_ids)

    # replace the annotations with the corresponding states
    return re.sub(
        r"JJPR:([^:]*):JJPR",
        lambda x: ", ".join(
            text.rich_str(id_to_state.get(part, "")) for part in x.group(1).split(",")
        ),
        logdata,
    )


def diagram(bookmarks: bool = False) -> str:
    bookmarks_part = 'self.bookmarks().map(|b| b.name()).join(",")' if bookmarks else ""
    descr = f'''separate(
        " ; ",
        self.description().first_line(),
        {bookmarks_part}
    )'''
    d = run("log", "-T", descr, "--config", "ui.graph.style=ascii", cap=True)
    d = d[:-4]  # remove trailing \n|\n~
    return f"\n{d}\n"


@contextmanager
def with_edit(rev: RevSet, new: bool = False):
    """Context manager to temporarily switch to a change and reset on exit.

    If the target ref is already the current commit, does nothing.
    If the current change is empty, creates a new empty commit with the same parent.
    """
    orig_change_id = change_id("@")
    orig_parents = parents_of(orig_change_id)
    targ_change_id = change_id(rev)

    if not new and orig_change_id == targ_change_id:
        log.debug(f"Already on target change {targ_change_id}, no edit needed.")
        yield
        return

    no_files = len(files_in(orig_change_id)) == 0
    no_descr = description_of(orig_change_id) == ""
    is_empty = no_files and no_descr
    try:
        co = "child of " if new else ""
        log.debug(f"Switching from {orig_change_id} to {co}{targ_change_id}.")
        run("new" if new else "edit", targ_change_id)
        yield
    finally:
        if is_empty:
            log.debug(f"Resetting to empty change with parents {orig_parents}.")
            run("new", *orig_parents)
        else:
            log.debug(f"Resetting back to original change {orig_change_id}.")
            run("edit", orig_change_id)


@contextmanager
def with_new(rev: RevSet):
    with with_edit(rev, new=True):
        yield
