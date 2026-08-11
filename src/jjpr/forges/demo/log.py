import hashlib

import httpx

from ...utils import cr, jj

# A handful of canned states/checks used to annotate `jj log`, cycled through
# deterministically based on each commit's change id.
_DEMO_LOG_STATES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Draft", "cyan", []),
    ("Needs Review", "yellow", [("lint", "green"), ("tests", "yellow")]),
    ("Accepted", "green", [("lint", "green"), ("tests", "green")]),
    ("Blocked", "red", [("lint", "green"), ("tests", "red")]),
]


def log_cmd(remote: str, args: list[str]) -> str:
    def _pr_ids_to_crs(pr_ids: list[str]) -> dict[str, cr.CodeReview]:
        return {pr_id: _demo_annotation(pr_id) for pr_id in pr_ids}

    return jj.log_with_annotations(
        args,
        "commit.change_id().normal_hex()",
        _pr_ids_to_crs,
    )


def _demo_annotation(seed: str) -> cr.CodeReview:
    name, color, checks = _DEMO_LOG_STATES[_stable_index(seed, len(_DEMO_LOG_STATES))]
    return cr.CodeReview(
        cr_id=str(seed),
        title="Fix bug",
        url=httpx.URL("https://example.com/fix-bug"),
        state=cr.State(name, color=color),
        checks=[
            cr.Blocker(name=check_name, color=check_color)
            for check_name, check_color in checks
        ],
        blockers=[],
        extra={"author": "alice", "branch": "feature/x"},
    )


def _check_to_str(name: str, color: str) -> str:
    icon = {"green": "✔", "red": "✗", "yellow": "…"}.get(color, "?")
    return f"[link=http://demo][{color}]{icon}[/{color}][/link]"


def _stable_index(seed: str, n: int) -> int:
    """A deterministic (but not predictable at a glance) index in [0, n)."""
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest, "big") % n
