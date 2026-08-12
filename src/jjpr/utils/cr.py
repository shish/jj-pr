import enum
import typing as t
from dataclasses import dataclass, field

import httpx
from rich.markup import escape


@dataclass
class ReviewState:
    name: str
    color: str

    def __rich__(self) -> str:
        return f"[{self.color}]{escape(self.name)}[/{self.color}]"


class CheckState(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    IN_PROGRESS = "in_progress"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass
class Check:
    name: str
    url: httpx.URL | None
    state: CheckState

    def __rich__(self) -> str:
        color = {
            CheckState.PASS: "green",
            CheckState.FAIL: "red",
            CheckState.IN_PROGRESS: "yellow",
            CheckState.OTHER: "grey",
            CheckState.UNKNOWN: "pink",
        }.get(self.state, "grey")
        t = f"[{color}]{escape(self.name)}[/{color}]"
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t


@dataclass
class CodeReview:
    cr_id: str
    title: str
    url: httpx.URL
    state: ReviewState
    checks: list[Check]
    unresolved_comments: int | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def __rich__(self) -> str:
        """
        Return a short string representation of the review state, with ANSI
        colour codes, suitable for including in `jj log` output.
        """
        parts = []
        parts.append(f"[link={self.url}]{self.state.__rich__()}[/link]")
        for check in self.checks:
            icon = {
                CheckState.PASS: "[green]✔[/green]",
                CheckState.FAIL: "[red]✗[/red]",
                CheckState.IN_PROGRESS: "[yellow]…[/yellow]",
                CheckState.OTHER: "[grey]?[/grey]",
                CheckState.UNKNOWN: "[pink]?[/pink]",
            }[check.state]
            parts.append(f"[link={check.url}]{icon}[/link]" if check.url else icon)
        if self.unresolved_comments:
            parts.append(f"[yellow]({self.unresolved_comments}!)[/yellow]")
        return " ".join(parts)


def json_default(obj: t.Any) -> t.Any:
    if isinstance(obj, httpx.URL):
        return str(obj)
    if isinstance(obj, CheckState):
        return str(obj.name)
    if hasattr(obj, "__dataclass_fields__"):
        return {
            field.name: getattr(obj, field.name)
            for field in obj.__dataclass_fields__.values()
        }
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )  # pragma: no cover
