import logging
import typing as t

from ...utils import cr
from .lib import info, util

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge_info = info.get_forge_info(remote)
    log.info(f"Listing diffs for {forge_info.remote_url} ({forge_info.project_id})")

    revs = _my_open_crs(forge_info)
    checks_by_diff = util.get_checks(
        forge_info.client,
        forge_info.forge_url,
        [rev["fields"]["diffPHID"] for rev in revs],
    )
    unresolved_by_rev = util.get_unresolved_counts(
        forge_info.client, [rev["id"] for rev in revs]
    )

    return [util.parse_cr(rev, checks_by_diff, unresolved_by_rev) for rev in revs]


def _my_open_crs(forge_info: info.PhabricatorInfo) -> list[dict[str, t.Any]]:
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
