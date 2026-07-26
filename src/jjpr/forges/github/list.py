import json
import logging

import httpx

from ...utils import cr, exec
from ._info import get_forge_info
from ._util import colour_state

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    f = get_forge_info(remote)
    log.info(f"Listing PRs for {f.remote_url} ({f.project_id})")
    prs = json.loads(
        exec.run(
            "gh",
            "pr",
            "list",
            "--repo",
            str(f.remote_url),
            "--author",
            "@me",
            "--json",
            "number,title,state,url,statusCheckRollup,isDraft,reviews",
        )
    )
    crs: list[cr.CodeReview] = []
    c2c = {
        "SUCCESS": "green",
        "PENDING": "yellow",
        "FAILURE": "red",
    }
    for pr in prs:
        # Merge status checks into a blockers string
        checks = [
            cr.Blocker(
                name=check["name"],
                color=c2c.get(check["conclusion"], "normal"),
                url=check["detailsUrl"],
            )
            for check in pr.get("statusCheckRollup", [])
        ]

        # Determine PR state based on draft status and reviews
        is_draft = pr.get("isDraft", False)
        reviews = pr.get("reviews", [])

        crs.append(
            cr.CodeReview(
                cr_id="#" + str(pr["number"]),
                title=cr.Title(pr["title"], url=httpx.URL(pr["url"])),
                state=colour_state(is_draft=is_draft, reviews=reviews),
                checks=checks,
                blockers=[],
            )
        )
    return crs
