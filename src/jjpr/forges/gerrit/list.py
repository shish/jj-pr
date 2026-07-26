import logging
import re

import httpx

from ...utils import cr
from ._info import get_forge_info
from ._util import colour_state, get_checks

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    """List the user's open changes in Gerrit, showing any blockers."""
    f = get_forge_info(remote)
    log.info(f"Listing open changes from {f.forge_url} ({f.project_id})")
    query = f"owner:self+status:open+project:{f.project_id}"
    changes_response = f.client.get(
        f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
    ).json()

    crs: list[cr.CodeReview] = []
    for change in changes_response:
        checks = []
        for check in get_checks(f.client, change["_number"]):
            if check.get("state") not in {"SUCCESSFUL", "NOT_RELEVANT"}:
                checks.append(
                    cr.Blocker(
                        name=check.get("checker_name", check["checker_uuid"]),
                        color=_check_color(check.get("state")),
                        url=httpx.URL(check["url"]) if check.get("url") else None,
                    )
                )

        blockers = []
        for req in change.get("submit_requirements", []):
            if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}:
                req_name = re.sub("[^A-Z]+", "", req["name"])
                blockers.append(cr.Blocker(req_name))

        crs.append(
            cr.CodeReview(
                cr_id="c" + str(change["_number"]),
                title=cr.Title(
                    change["subject"],
                    url=f.forge_url.join(f"/c/{change['_number']}"),
                ),
                state=colour_state(
                    is_private=change.get("is_private", False),
                    work_in_progress=change.get("work_in_progress", False),
                    blockers=len(blockers) > 0,
                    url=f.forge_url.join(f"/c/{change['_number']}"),
                ),
                checks=checks,
                blockers=blockers,
            )
        )

    return crs


def _check_color(state: str | None) -> str:
    return {
        "SUCCESSFUL": "green",
        "NOT_RELEVANT": "green",
        "FAILED": "red",
    }.get(state or "", "yellow")
