import typing as t
from dataclasses import dataclass, field

import httpx
from rich.markup import escape

from . import text


@dataclass
class Title:
    text: str
    url: httpx.URL | None = None

    def __str__(self) -> str:
        return self.text

    def __rich__(self) -> str:
        t = escape(self.text)
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t


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
class State:
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

    def __str__(self) -> str:
        return text.rich_str(self)


@dataclass
class CodeReview:
    cr_id: str
    title: Title
    state: State
    checks: list[Blocker]
    blockers: list[Blocker]
    extra: dict[str, str] = field(default_factory=dict)


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
