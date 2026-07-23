import hashlib
import logging
import typing as t

import httpx

from ...utils import jj, text
from .. import cr
from ..base import Forge

log = logging.getLogger(__name__)

# A handful of canned CRs, chosen to show off every state/check/blocker
# combination that `jj pr list` knows how to render.
_DEMO_CRS: list[dict[str, t.Any]] = [
    {
        "cr_id": "#101",
        "title": "Add dark mode toggle",
        "state": ("Draft", "cyan"),
        "checks": [("lint", "red"), ("tests", "green")],
        "blockers": [],
    },
    {
        "cr_id": "#102",
        "title": "Fix flaky retry logic",
        "state": ("Needs Review", "yellow"),
        "checks": [("lint", "green"), ("tests", "yellow")],
        "blockers": [("Code-Review", "yellow")],
    },
    {
        "cr_id": "#103",
        "title": "Refactor auth middleware",
        "state": ("Accepted", "green"),
        "checks": [("lint", "green"), ("tests", "green")],
        "blockers": [],
    },
    {
        "cr_id": "#104",
        "title": "Bump dependency versions",
        "state": ("Blocked", "red"),
        "checks": [("lint", "green"), ("tests", "red")],
        "blockers": [("Build", "red"), ("Code-Review", "yellow")],
    },
]

# A handful of canned states/checks used to annotate `jj log`, cycled through
# deterministically based on each commit's change id.
_DEMO_LOG_STATES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Draft", "cyan", []),
    ("Needs Review", "yellow", [("lint", "green"), ("tests", "yellow")]),
    ("Accepted", "green", [("lint", "green"), ("tests", "green")]),
    ("Blocked", "red", [("lint", "green"), ("tests", "red")]),
]


class Demo(Forge):
    """A fake forge that returns canned data instead of talking to a server.

    Useful for trying out `jj pr` without needing a real GitHub/Gerrit/
    Phabricator account, or for taking screenshots and writing docs.
    """

    def __init__(self, remote: str):
        super().__init__(remote)
        self.forge_url = httpx.URL("https://demo.example.com")
        self.project_id = "demo/repo"

    def upload_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
        pre_commit: bool = True,
    ) -> None:
        pass

    def download_cr(self, identifier: str) -> None:
        pass

    def rebase_crs(self, change_ids: list[jj.ChangeID]) -> None:
        pass

    def list_crs(self) -> list[cr.CodeReview]:
        return [
            cr.CodeReview(
                forge=self,
                cr_id=demo["cr_id"],
                title=cr.Title(
                    demo["title"],
                    url=self.forge_url.join(demo["cr_id"].lstrip("#")),
                ),
                state=cr.State(demo["state"][0], color=demo["state"][1]),
                checks=[
                    cr.Blocker(name, color=color) for name, color in demo["checks"]
                ],
                blockers=[
                    cr.Blocker(name, color=color) for name, color in demo["blockers"]
                ],
            )
            for demo in _DEMO_CRS
        ]

    def log(self, args: list[str]) -> str:
        def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
            return {pr_id: _demo_annotation(pr_id) for pr_id in pr_ids}

        return jj.log_with_annotations(
            args,
            "commit.change_id().normal_hex()",
            _pr_ids_to_states,
        )


def _demo_annotation(seed: str) -> str:
    name, color, checks = _DEMO_LOG_STATES[_stable_index(seed, len(_DEMO_LOG_STATES))]
    state = cr.State(name, color=color, url=httpx.URL("http://demo"))
    return text.rich_str(state, *[_check_to_str(name, color) for name, color in checks])


def _check_to_str(name: str, color: str) -> str:
    icon = {"green": "✔", "red": "✗", "yellow": "…"}.get(color, "?")
    return f"[link=http://demo][{color}]{icon}[/{color}][/link]"


def _stable_index(seed: str, n: int) -> int:
    """A deterministic (but not predictable at a glance) index in [0, n)."""
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest, "big") % n
