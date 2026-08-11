import re
import typing as t

import httpx

from ....utils import cr
from .client import GerritClient


def _check_color(state: str | None) -> str:
    return {
        "SUCCESSFUL": "green",
        "NOT_RELEVANT": "green",
        "FAILED": "red",
    }.get(state or "", "yellow")


def parse_cr(
    change: dict[str, t.Any],
    client: GerritClient,
    forge_url: httpx.URL,
) -> cr.CodeReview:
    checks = [
        cr.Blocker(
            name=check.get("checker_name", check["checker_uuid"]),
            color=_check_color(check.get("state")),
            url=httpx.URL(check["url"]) if check.get("url") else None,
        )
        for check in get_checks(client, change["_number"])
        if check.get("state") not in {"SUCCESSFUL", "NOT_RELEVANT"}
    ]
    blockers = [
        cr.Blocker(re.sub("[^A-Z]+", "", req["name"]))
        for req in change.get("submit_requirements", [])
        if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}
    ]
    return cr.CodeReview(
        cr_id="c" + str(change["_number"]),
        title=change["subject"],
        url=forge_url.join(f"/c/{change['_number']}"),
        state=colour_state(
            is_private=change.get("is_private", False),
            work_in_progress=change.get("work_in_progress", False),
            blockers=len(blockers) > 0,
        ),
        checks=checks,
        blockers=blockers,
        unresolved_comments=change.get("unresolved_comment_count", 0),
    )


def get_checks(client: GerritClient, change_number: int) -> list[dict[str, t.Any]]:
    """Fetch CI check statuses for a change via the Gerrit checks plugin.

    Returns an empty list if the checks plugin isn't installed on this
    Gerrit instance.
    """
    try:
        response = client.get(
            f"changes/{change_number}/revisions/current/checks?o=CHECKER"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return []
        raise
    return response.json()


def colour_state(
    is_private: bool = False,
    work_in_progress: bool = False,
    blockers: bool = False,
) -> cr.State:
    if is_private:
        state = "Private"
        color = "cyan"
    elif work_in_progress:
        state = "Draft"
        color = "cyan"
    elif blockers:
        state = "Blocked"
        color = "yellow"
    else:
        state = "Accepted"
        color = "green"

    return cr.State(state, color=color)
