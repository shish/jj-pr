import logging
import typing as t

import httpx

from ...utils import cr
from .lib import client, info, util

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge_info = info.get_forge_info(remote)
    log.info(f"Listing diffs for {forge_info.remote_url} ({forge_info.project_id})")
    revs = _my_open_crs(forge_info)
    checks_by_diff = _get_checks(
        forge_info, [rev["fields"]["diffPHID"] for rev in revs]
    )
    crs: list[cr.CodeReview] = []
    for rev in revs:
        checks = [
            cr.Blocker(
                name=check["name"],
                color=util.check_color(check["status"]),
                url=check["url"],
            )
            for check in checks_by_diff.get(rev["fields"]["diffPHID"], [])
        ]
        crs.append(
            cr.CodeReview(
                cr_id="D" + str(rev["id"]),
                title=cr.Title(
                    text=rev["fields"]["title"],
                    url=httpx.URL(rev["fields"]["uri"]),
                ),
                state=util.colour_state(
                    state=rev["fields"]["status"]["name"],
                    url=httpx.URL(rev["fields"]["uri"]),
                ),
                checks=checks,
                blockers=[],
            )
        )
    return crs


def _my_open_crs(forge_info: info.ForgeInfo) -> list[dict[str, t.Any]]:
    myPHID = forge_info.client.call("user.whoami")["phid"]
    revs = forge_info.client.call(
        "differential.revision.search",
        constraints={
            "authorPHIDs": [myPHID],
            "repositoryPHIDs": [
                util.callsign_to_phid(forge_info.client, forge_info.project_id)
            ],
            "statuses": [
                "draft",
                "needs-review",
                "needs-revision",
                "accepted",
                "changes-planned",
            ],
        },
    )["data"]
    return revs


def _get_checks(
    forge_info: info.ForgeInfo, diff_phids: list[client.PhId]
) -> dict[client.PhId, list[dict[str, t.Any]]]:
    """Fetch Harbormaster build/check statuses for a set of diffs.

    Returns a mapping of diff PHID to a list of {name, status, url}
    dicts, one per Harbormaster build associated with that diff.
    """
    diff_phids = [phid for phid in diff_phids if phid]
    if not diff_phids:
        return {}

    buildables = forge_info.client.call(
        "harbormaster.buildable.search",
        constraints={"objectPHIDs": diff_phids},
    )["data"]
    if not buildables:
        return {}

    buildable_phid_to_diff_phid = {
        buildable["phid"]: buildable["fields"]["objectPHID"] for buildable in buildables
    }
    builds = forge_info.client.call(
        "harbormaster.build.search",
        constraints={"buildables": list(buildable_phid_to_diff_phid)},
    )["data"]

    checks: dict[client.PhId, list[dict[str, t.Any]]] = {}
    for build in builds:
        diff_phid = buildable_phid_to_diff_phid.get(build["fields"]["buildablePHID"])
        if not diff_phid:
            continue
        checks.setdefault(diff_phid, []).append(
            {
                "name": build["fields"]["name"],
                "status": build["fields"]["buildStatus"]["value"],
                "url": forge_info.forge_url.join(f"/harbormaster/build/{build['id']}/"),
            }
        )
    return checks
