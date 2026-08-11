import typing as t
from dataclasses import dataclass, field

import httpx
from rich.markup import escape
from typing_extensions import override

from . import text


@dataclass
class State:
    name: str
    color: str

    def __rich__(self) -> str:
        return f"[{self.color}]{escape(self.name)}[/{self.color}]"

    @override
    def __str__(self) -> str:
        return text.rich_str(self)


@dataclass
class Blocker:
    name: str
    color: str | None = None
    url: httpx.URL | None = None

    def __rich__(self) -> str:
        t = escape(self.name)
        if self.color:
            t = f"[{self.color}]{t}[/{self.color}]"
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t


@dataclass
class CodeReview:
    cr_id: str
    title: str
    url: httpx.URL
    state: State
    checks: list[Blocker]
    blockers: list[Blocker]
    unresolved_comments: int | None = None
    extra: dict[str, str] = field(default_factory=dict)

    # Short render for `jj pr log` -- `jj pr list` will render each element
    # in a table in full-size mode
    @override
    def __str__(self) -> str:
        parts = []
        parts.append(self.state.__rich__())
        for check in self.checks:
            parts.append(check.__rich__())
        for blocker in self.blockers:
            parts.append(blocker.__rich__())
        if self.unresolved_comments:
            parts.append(f"[yellow]({self.unresolved_comments}!)[/yellow]")
        return text.rich_str(" ".join(str(x) for x in parts if x))


def json_default(obj: t.Any) -> t.Any:
    if isinstance(obj, httpx.URL):
        return str(obj)
    if hasattr(obj, "__dataclass_fields__"):
        return {
            field.name: getattr(obj, field.name)
            for field in obj.__dataclass_fields__.values()
        }
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )  # pragma: no cover
