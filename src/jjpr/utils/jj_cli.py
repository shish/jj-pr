#!/usr/bin/env python3
"""Manual testing script for jj.py"""

import logging

import typer
from rich.pretty import pretty_repr

from . import jj

log = logging.getLogger(__name__)

app = typer.Typer(help=__doc__)


@app.command(name="bookmarks")
def bookmarks():
    result = jj.bookmarks()
    typer.echo(pretty_repr(result))


@app.command(name="closest-work")
def closest_work_cmd():
    result = jj.closest_work()
    typer.echo(result)


@app.command(name="pushable-stack")
def pushable_stack_cmd():
    result = jj.pushable_stack()
    for changeid in result:
        typer.echo(changeid)


@app.command(name="checkable-stack")
def checkable_stack_cmd():
    result = jj.checkable_stack()
    for changeid in result:
        typer.echo(changeid)


@app.command(name="change-id")
def revset_to_changeid_cmd(
    revset: str = typer.Argument(..., help="The revset expression to convert"),
):
    result = jj.change_id(revset)
    typer.echo(result)


@app.command(name="parents-of")
def parents_of_cmd(
    revset: str = typer.Argument(..., help="The revset expression to convert"),
):
    change_id = jj.change_id(revset)
    result = jj.parents_of(change_id)
    for parent in result:
        typer.echo(parent)


@app.command("branches-pointing-to")
def branches_pointing_to_cmd(
    rev: str = typer.Argument(..., help="The revset expressions to convert"),
):
    changes = jj.change_ids(rev) if rev else jj.checkable_stack()
    for change_id in changes:
        result = jj.branches_pointing_to(change_id)
        for branch in result:
            typer.echo(branch)


@app.command("files-in")
def files_in_cmd(
    revset: str = typer.Argument(..., help="The revset expression to convert"),
):
    change_id = jj.change_id(revset)
    result = jj.files_in(change_id)
    for file in result:
        typer.echo(file)


@app.command("description-of")
def description_of_cmd(
    revset: str = typer.Argument(..., help="The revset expression to convert"),
):
    change_id = jj.change_id(revset)
    result = jj.description_of(change_id)
    typer.echo(result)


def main():
    logging.basicConfig(level=logging.DEBUG)
    app()


if __name__ == "__main__":
    main()
