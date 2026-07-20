import json
import logging
import sys
import typing as t
from pathlib import Path

import typer

from . import cmds, exc
from .forges.cr import json_default
from .utils import jj

app = typer.Typer(
    help="Unified CLI for multiple code review forges",
    add_completion=False,
)
log = logging.getLogger(__name__)

OutputFormat = t.Literal["table", "json"]


class GlobalOptions:
    def __init__(self, repo: cmds.Repo, format: OutputFormat) -> None:
        self.repo = repo
        self.format = format


@app.callback(invoke_without_command=False)
def main(
    ctx: typer.Context,
    path: Path | None = typer.Option(
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

    if not path:
        try:
            path = Path(jj.root())
        except Exception as e:
            raise exc.UserError(f"Can't detect current repository: {e}")

    ctx.obj = GlobalOptions(cmds.Repo(path, remote), format)


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
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        if pre_commit:
            cmds.pre_commit_stack(ref)
        r.remote.upload_cr(ref, draft=draft, message=message, pre_commit=pre_commit)


@app.command("rebase")
def rebase_command(
    ctx: typer.Context,
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Rebase all local branches; if not set, only rebase the current branch",
    ),
) -> None:
    """Pull from remote and rebase current stack."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        jj.git_fetch(remote=r.remote.remote)
        jj.rebase(d="trunk()", r="mutable()" if all else "trunk()..@")


@app.command("download")
def download_command(
    ctx: typer.Context,
    identifier: str = typer.Argument(None, help="PR/Diff/CR ID"),
) -> None:
    """Download a PR/CR/Diff from the forge."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        r.remote.download_cr(identifier)


@app.command("list")
def list_command(
    ctx: typer.Context,
) -> None:
    """List my open PRs/CRs/Diffs for the current project."""
    gos = t.cast(GlobalOptions, ctx.obj)
    r = gos.repo
    with r.chdir():
        items = r.remote.list_crs()

    # Output the results
    if gos.format == "json":
        print(json.dumps(items, indent=4, default=json_default))
    else:
        if items:
            cmds.display_list(items)
        else:
            print("No items found.")


@app.command("pre-commit")
def pre_commit_command(
    ctx: typer.Context,
    ref: str | None = typer.Argument(None, help="Ref to check"),
) -> None:
    """Run pre-commit hooks."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        cmds.pre_commit_stack(ref)


@app.command("log")
def log_command(
    ctx: typer.Context,
) -> None:
    """Run `jj log` with annotated extra output for code review status."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        print(r.remote.log(ctx.args))


def run() -> None:
    try:
        app()
    except exc.UserError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
