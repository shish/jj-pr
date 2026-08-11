import typing as t

from ...utils import cr
from .lib import info

# A handful of canned CRs, chosen to show off every state/check/blocker
# combination that `jj pr list` knows how to render.
_DEMO_CRS: list[dict[str, t.Any]] = [
    {
        "cr_id": "#101",
        "title": "Add dark mode toggle",
        "state": ("Draft", "cyan"),
        "checks": [("lint", "red"), ("tests", "green")],
        "blockers": [],
        "unresolved_comments": 2,
    },
    {
        "cr_id": "#102",
        "title": "Fix flaky retry logic",
        "state": ("Needs Review", "yellow"),
        "checks": [("lint", "green"), ("tests", "yellow")],
        "blockers": [("Code-Review", "yellow")],
        "unresolved_comments": 1,
    },
    {
        "cr_id": "#103",
        "title": "Refactor auth middleware",
        "state": ("Accepted", "green"),
        "checks": [("lint", "green"), ("tests", "green")],
        "blockers": [],
        "unresolved_comments": 0,
    },
    {
        "cr_id": "#104",
        "title": "Bump dependency versions",
        "state": ("Blocked", "red"),
        "checks": [("lint", "green"), ("tests", "red")],
        "blockers": [("Build", "red"), ("Code-Review", "yellow")],
        "unresolved_comments": 0,
    },
]


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge_info = info.get_forge_info(remote)
    return [
        cr.CodeReview(
            cr_id=demo["cr_id"],
            title=demo["title"],
            url=forge_info.forge_url.join(demo["cr_id"].lstrip("#")),
            state=cr.State(demo["state"][0], color=demo["state"][1]),
            checks=[cr.Blocker(name, color=color) for name, color in demo["checks"]],
            blockers=[
                cr.Blocker(name, color=color) for name, color in demo["blockers"]
            ],
            unresolved_comments=demo["unresolved_comments"],
        )
        for demo in _DEMO_CRS
    ]
