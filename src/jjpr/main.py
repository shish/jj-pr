import json
import logging
import os
import shlex
import sys
import typing as t
from pathlib import Path

import typer
from rich import markup
from rich.console import Console
from rich.table import Table

from .forges import detect
from .utils import cr, exc, exec, git, jj

app = typer.Typer(
    help="Unified CLI for multiple code review forges",
    add_completion=False,
)
log = logging.getLogger(__name__)

OutputFormat = t.Literal["table", "json"]


class GlobalOptions:
    def __init__(self, repository: Path, remote: str, format: OutputFormat) -> None:
        self.repository = repository
        self.remote = remote
        self.format = format
        self.backend = detect.get_forge(remote)
        self.original_cwd = Path.cwd()
        os.chdir(repository)


@app.callback(invoke_without_command=False)
def main(
    ctx: typer.Context,
    repository: Path | None = typer.Option(
        None,
        "--repository",
        help="Path to respository to operate on",
    ),
    remote: str | None = typer.Option(
        None, "--remote", help="Which remote to work with"
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
        count=True,
    ),
    format: OutputFormat = typer.Option(
        "table",
        "--format",
        hidden=True,
        help="Output format (unstable, for testing only)",
    ),
) -> None:
    log_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    logging.basicConfig(level=log_level)
    # we can log our own HTTP I/O
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)

    if not repository:
        try:
            repository = Path(jj.root())
        except Exception as e:
            raise exc.UserError(f"Can't detect current repository: {e}")

    remote = remote or git.default_remote()
    ctx.obj = GlobalOptions(repository, remote, format)


@app.command("upload")
def upload_command(
    ctx: typer.Context,
    ref: str | None = typer.Argument(None, help="Ref to push"),
    pre_commit: bool = typer.Option(
        True,
        "--pre-commit/--no-pre-commit",
        help="Run or skip pre-commit hooks",
    ),
    draft: bool = typer.Option(
        False,
        "--draft",
        help="Create as a draft/WIP",
    ),
    message: str | None = typer.Option(
        None,
        "-m",
        "--message",
        help="Commit/PR message",
    ),
) -> None:
    """Upload current stack to the forge."""
    go = t.cast(GlobalOptions, ctx.obj)
    if pre_commit:
        changes = jj.change_ids(jj.revset(ref)) if ref else jj.pushable_stack()
        _pre_commit_stack(changes)
    go.backend.upload_cmd(
        go.remote, jj.revset(ref), draft=draft, message=message, pre_commit=pre_commit
    )


@app.command("rebase")
def rebase_command(
    ctx: typer.Context,
    all_prs: bool = typer.Option(
        False,
        "--all-prs",
        "-a",
        help="Rebase all branches that have an associated CR; skip branches without one",
    ),
    all_branches: bool = typer.Option(
        False,
        "--all-branches",
        "-A",
        help="Rebase all branches; use the default merge target for those without a CR",
    ),
    revset: str | None = typer.Argument(None, help="Revset to rebase"),
) -> None:
    """Pull from remote and rebase current stack."""
    go = t.cast(GlobalOptions, ctx.obj)
    if all_prs or all_branches:
        revset = "mutable()"
    elif revset:
        pass  # revset = revset
    else:
        revset = "@"
    roots = jj.change_ids(jj.revset(f"roots(mutable()::{revset})"))
    log.info(f"Rebasing revset: {revset} ({roots})")
    go.backend.rebase_cmd(go.remote, roots, skip_without_cr=all_prs)


@app.command("download")
def download_command(
    ctx: typer.Context,
    identifier: str = typer.Argument(None, help="PR/Diff/CR ID"),
) -> None:
    """Download a PR/CR/Diff from the forge."""
    go = t.cast(GlobalOptions, ctx.obj)
    go.backend.download_cmd(go.remote, identifier)


@app.command("list")
def list_command(
    ctx: typer.Context,
) -> None:
    """List my open PRs/CRs/Diffs for the current project."""
    go = t.cast(GlobalOptions, ctx.obj)
    items = go.backend.list_cmd(go.remote)

    # Output the results
    if go.format == "json":
        print(json.dumps(items, indent=4, default=cr.json_default))
    elif not items:
        print("No items found.")
    else:
        console = Console()

        all_extra_keys = set()
        for item in items:
            all_extra_keys.update(item.extra.keys())

        table = Table()
        table.add_column("ID", style="blue", min_width=4)
        table.add_column("Title", style="green")
        table.add_column("State", width=12)
        table.add_column("Checks", min_width=8)
        table.add_column("Comments", min_width=8)
        for key in sorted(all_extra_keys):
            table.add_column(key.title(), style="magenta")

        for item in items:
            table.add_row(
                item.cr_id,
                f"[link={item.url}]{markup.escape(item.title)}[/link]",
                item.state,
                ", ".join(b.__rich__() for b in item.checks),
                str(item.unresolved_comments),
                *[item.extra.get(key, "") for key in sorted(all_extra_keys)],
            )

        console.print(table)


@app.command("pre-commit")
def pre_commit_command(
    ctx: typer.Context,
    ref: str | None = typer.Argument(None, help="Ref to check"),
) -> None:
    """Run pre-commit hooks on a stack of changes."""
    # go = t.cast(GlobalOptions, ctx.obj)
    changes = jj.change_ids(jj.revset(ref)) if ref else jj.checkable_stack()
    _pre_commit_stack(changes)


def _pre_commit_stack(changes: list[jj.ChangeId]) -> None:
    pc_cmd = Path(".git/hooks/pre-commit")
    if not pc_cmd.exists():
        log.info("No pre-commit configuration found, skipping")
        return

    for n, change_id in enumerate(changes):
        if n > 0:
            print("=" * 80)
        _pre_commit_change(change_id, str(pc_cmd))


def _pre_commit_change(change_id: jj.ChangeId, pc_cmd: str) -> None:
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


@app.command("log")
def log_command(
    ctx: typer.Context,
) -> None:
    """Run `jj log` with annotated extra output for code review status."""
    go = t.cast(GlobalOptions, ctx.obj)
    print(go.backend.log_cmd(go.remote, ctx.args))


def run() -> None:
    try:
        app()
    except exc.UserError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
