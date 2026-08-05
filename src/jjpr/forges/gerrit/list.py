import logging
import re

import httpx

from ...utils import cr
from .lib import info, util

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    """List the user's open changes in Gerrit, showing any blockers."""
    forge_info = info.get_forge_info(remote)
    log.info(
        f"Listing open changes from {forge_info.forge_url} ({forge_info.project_id})"
    )
    query = f"owner:self+status:open+project:{forge_info.project_id}"
    changes_response = forge_info.client.get(
        f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
    ).json()

    crs: list[cr.CodeReview] = []
    for change in changes_response:
        checks = []
        for check in util.get_checks(forge_info.client, change["_number"]):
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
                    url=forge_info.forge_url.join(f"/c/{change['_number']}"),
                ),
                state=util.colour_state(
                    is_private=change.get("is_private", False),
                    work_in_progress=change.get("work_in_progress", False),
                    blockers=len(blockers) > 0,
                    url=forge_info.forge_url.join(f"/c/{change['_number']}"),
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
