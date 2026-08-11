import httpx

from ...utils import cr, jj

# A handful of canned states/checks used to annotate `jj log`, cycled through
# deterministically based on each commit's change id.
_DEMO_LOG_STATES: list[tuple[str, str, list[tuple[str, cr.CheckState]]]] = [
    (
        "Draft",
        "cyan",
        [],
    ),
    (
        "Needs Review",
        "yellow",
        [("lint", cr.CheckState.PASS), ("tests", cr.CheckState.IN_PROGRESS)],
    ),
    (
        "Accepted",
        "green",
        [("lint", cr.CheckState.PASS), ("tests", cr.CheckState.PASS)],
    ),
    (
        "Blocked",
        "red",
        [("lint", cr.CheckState.PASS), ("tests", cr.CheckState.FAIL)],
    ),
]


def log_cmd(remote: str, args: list[str]) -> str:
    def _pr_ids_to_crs(pr_ids: list[str]) -> dict[str, cr.CodeReview]:
        return {pr_id: _demo_annotation(pr_id) for pr_id in pr_ids}

    return jj.log_with_annotations(
        args,
        "commit.change_id().normal_hex()",
        _pr_ids_to_crs,
    )


def _demo_annotation(change_id_hex: str) -> cr.CodeReview:
    name, color, checks = _DEMO_LOG_STATES[
        int(change_id_hex, 16) % len(_DEMO_LOG_STATES)
    ]
    return cr.CodeReview(
        cr_id=change_id_hex[:8],
        title="Fix bug",
        url=httpx.URL("https://example.com/fix-bug"),
        state=cr.ReviewState(name, color=color),
        checks=[
            cr.Check(
                name=check_name,
                url=httpx.URL("http://example.com"),
                state=check_state,
            )
            for check_name, check_state in checks
        ],
    )
