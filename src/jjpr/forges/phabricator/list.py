import logging
import typing as t

import httpx

from ...utils import cr
from ._client import PhabricatorClient, PhID
from ._info import get_forge_info
from ._util import callsign_to_phid, check_color, colour_state

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge = get_forge_info(remote)
    log.info(f"Listing diffs for {forge.remote_url} ({forge.project_id})")
    revs = _my_open_crs(forge.client, forge.project_id)
    checks_by_diff = _get_checks(
        forge.client, forge.forge_url, [rev["fields"]["diffPHID"] for rev in revs]
    )
    crs: list[cr.CodeReview] = []
    for rev in revs:
        checks = [
            cr.Blocker(
                name=check["name"],
                color=check_color(check["status"]),
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
                state=colour_state(
                    state=rev["fields"]["status"]["name"],
                    url=httpx.URL(rev["fields"]["uri"]),
                ),
                checks=checks,
                blockers=[],
            )
        )
    return crs


def _my_open_crs(client: PhabricatorClient, callsign: str) -> list[dict[str, t.Any]]:
    myPHID = client.call("user.whoami")["phid"]
    revs = client.call(
        "differential.revision.search",
        constraints={
            "authorPHIDs": [myPHID],
            "repositoryPHIDs": [callsign_to_phid(client, callsign)],
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
    client: PhabricatorClient, base_url: httpx.URL, diff_phids: list[PhID]
) -> dict[PhID, list[dict[str, t.Any]]]:
    """Fetch Harbormaster build/check statuses for a set of diffs.

    Returns a mapping of diff PHID to a list of {name, status, url}
    dicts, one per Harbormaster build associated with that diff.
    """
    diff_phids = [phid for phid in diff_phids if phid]
    if not diff_phids:
        return {}

    buildables = client.call(
        "harbormaster.buildable.search",
        constraints={"objectPHIDs": diff_phids},
    )["data"]
    if not buildables:
        return {}

    buildable_phid_to_diff_phid = {
        buildable["phid"]: buildable["fields"]["objectPHID"] for buildable in buildables
    }
    builds = client.call(
        "harbormaster.build.search",
        constraints={"buildables": list(buildable_phid_to_diff_phid)},
    )["data"]

    checks: dict[PhID, list[dict[str, t.Any]]] = {}
    for build in builds:
        diff_phid = buildable_phid_to_diff_phid.get(build["fields"]["buildablePHID"])
        if not diff_phid:
            continue
        checks.setdefault(diff_phid, []).append(
            {
                "name": build["fields"]["name"],
                "status": build["fields"]["buildStatus"]["value"],
                "url": base_url.join(f"/harbormaster/build/{build['id']}/"),
            }
        )
    return checks
