import logging
import os
import shlex
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .forges import cr, detect
from .utils import exec, jj, exc

log = logging.getLogger(__name__)


class Repo:
    def __init__(
        self,
        path: Path,
        remote: str | None,
    ):
        self.path = path.resolve()
        with self.chdir():
            default_remote = exec.run("git", "remote").splitlines()[0]
            forge = detect.get_forge(remote or default_remote)
        self.remote = forge

    @contextmanager
    def chdir(self):
        """Context manager to temporarily change the working directory
        to the root of the checked-out repository."""
        original_dir = Path.cwd()
        try:
            os.chdir(self.path)
            yield
        finally:
            os.chdir(original_dir)


def pre_commit_stack(ref: str | None) -> None:
    """Run pre-commit hooks on a stack of changes."""
    pc_cmd = Path(".git/hooks/pre-commit")
    if not pc_cmd.exists():
        log.info("No pre-commit configuration found, skipping")
        return

    changes = jj.change_ids(ref) if ref else jj.checkable_stack()
    for n, change_id in enumerate(changes):
        if n > 0:
            print("=" * 80)
        pre_commit_change(change_id, str(pc_cmd))


def pre_commit_change(change_id: str, pc_cmd: str) -> None:
    with jj.with_edit(change_id):
        files = jj.files_in(change_id)
        files = [f for f in files if Path(f).exists()]
        descr = (jj.description_of(change_id).splitlines() or ["(untitled)"])[0]
        print(f'Checking "{descr}" ({change_id})')
        print(f"Affected files: {shlex.join(files)}")
        try:
            exec.run("git", "add", "--all", cap=False)
            exec.run(pc_cmd, cap=False)
        except Exception:
            raise exc.UserError(f"pre-commit checks failed for change {change_id}")


def display_list(items: list[cr.CodeReview]) -> None:
    """Display a list of code review items in a formatted table."""
    console = Console()

    all_extra_keys = set()
    for item in items:
        all_extra_keys.update(item.extra.keys())

    table = Table()
    table.add_column("ID", style="blue", min_width=4)
    table.add_column("Title", style="green")
    table.add_column("State", width=12)
    table.add_column("Checks", min_width=8)
    table.add_column("Blockers", min_width=8)
    for key in sorted(all_extra_keys):
        table.add_column(key.title(), style="magenta")

    for item in items:
        table.add_row(
            item.cr_id,
            item.title,
            item.state,
            ", ".join(b.__rich__() for b in item.checks),
            ", ".join(b.__rich__() for b in item.blockers),
            *[item.extra.get(key, "") for key in sorted(all_extra_keys)],
        )

    console.print(table)
