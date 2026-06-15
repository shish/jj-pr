import logging
import subprocess
from contextlib import contextmanager

log = logging.getLogger(__name__)

# Type aliases
ChangeID = str
RevSet = str


class JjError(Exception):
    pass


def run(*args: str) -> str:
    """Run a jj command and return stdout."""
    try:
        result = subprocess.run(
            ["jj"] + list(args),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise JjError(f"jj command failed: {' '.join(args)}") from e
    except FileNotFoundError as e:
        raise JjError("jj command not found") from e


def revset_to_changeid(revset: RevSet) -> ChangeID:
    return run("log", "-r", revset, "--no-graph", "-T", "self.change_id().short()")


def closest_work() -> ChangeID:
    return revset_to_changeid("heads(::@ & mutable() & (~empty() | merges()))")


def current_stack() -> list[ChangeID]:
    output = run(
        "log",
        "-r",
        "trunk()..heads(::@ & mutable() & (~empty() | merges()))",
        "--no-graph",
        "--reversed",
        "-T",
        'self.change_id().short() ++ "\n"',
    )
    return [c for c in output.split("\n") if c]


def change_parents(change_id: ChangeID) -> list[ChangeID]:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "parents.map(|p| p.change_id().short()).join('\\n')",
    )
    return [p for p in output.split("\n") if p]


def files_in(change_id: ChangeID) -> list[str]:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "self.diff().files().map(|f| f.path()).join('\n')",
    )
    return [f for f in output.split("\n") if f]


@contextmanager
def with_edit(rev: RevSet):
    """Context manager to temporarily switch to a change and reset on exit.

    If the target ref is already the current commit, does nothing.
    If the current change is empty, creates a new empty commit with the same parent.
    """
    original_change_id = revset_to_changeid("@")
    original_parents = change_parents(original_change_id)
    target_change_id = revset_to_changeid(rev)

    if original_change_id == target_change_id:
        log.debug(f"Already on target change {target_change_id}, no edit needed.")
        yield
        return

    is_empty = files_in(original_change_id) == []
    try:
        log.debug(f"Switching from change {original_change_id} to {target_change_id}.")
        run("edit", target_change_id)
        yield
    finally:
        if is_empty:
            run("new", *original_parents)
            log.debug(f"Creating new empty change with parents {original_parents}.")
            run("new", *original_parents)
        else:
            log.debug(f"Resetting back to original change {original_change_id}.")
            run("edit", original_change_id)
