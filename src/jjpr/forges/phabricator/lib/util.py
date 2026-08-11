import typing as t

import httpx

from ....utils import cr
from .client import PhabricatorClient, PhId, PhRevNum


def callsign_to_phid(client: PhabricatorClient, callsign: str) -> PhId:
    return client.call(
        "diffusion.repository.search",
        constraints={"callsigns": [callsign]},
    )["data"][0]["phid"]


def get_checks(
    client: PhabricatorClient, forge_url: httpx.URL, diff_phids: list[PhId]
) -> dict[PhId, list[dict[str, t.Any]]]:
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

    checks: dict[PhId, list[dict[str, t.Any]]] = {}
    for build in builds:
        diff_phid = buildable_phid_to_diff_phid.get(build["fields"]["buildablePHID"])
        if not diff_phid:
            continue
        checks.setdefault(diff_phid, []).append(
            {
                "name": build["fields"]["name"],
                "status": build["fields"]["buildStatus"]["value"],
                "url": forge_url.join(f"/harbormaster/build/{build['id']}/"),
            }
        )
    return checks


def colour_state(state: str) -> cr.State:
    c = {
        "Draft": "cyan",
        "Changes Planned": "cyan",
        "Rejected": "red",
        "Needs Review": "yellow",
        "Accepted": "green",
        "Closed": "grey",
        "Abandoned": "grey",
    }.get(state, "yellow")
    return cr.State(state, color=c)


def parse_cr(
    rev: dict[str, t.Any],
    checks_by_diff: dict[PhId, list[dict[str, t.Any]]],
    unresolved_by_rev: dict[PhRevNum, int],
) -> cr.CodeReview:
    raw_checks = checks_by_diff.get(PhId(rev["fields"]["diffPHID"]), [])
    checks = [
        cr.Blocker(
            name=check["name"],
            color=check_color(check["status"]),
            url=check["url"],
        )
        for check in raw_checks
    ]
    return cr.CodeReview(
        cr_id="D" + str(rev["id"]),
        title=rev["fields"]["title"],
        url=httpx.URL(rev["fields"]["uri"]),
        state=colour_state(rev["fields"]["status"]["name"]),
        checks=checks,
        blockers=[],
        unresolved_comments=unresolved_by_rev.get(PhRevNum(rev["id"]), 0),
    )


def get_unresolved_counts(
    client: PhabricatorClient, revision_nums: list[PhRevNum]
) -> dict[PhRevNum, int]:
    """Count unresolved (not-done) inline comments per revision PHID."""
    if not revision_nums:
        return {}

    counts = {}
    for rev_num in revision_nums:
        txns = client.call(
            "transaction.search",
            objectIdentifier="D" + str(rev_num),
        )["data"]

        """
        txn = {
            "id": 10,
            "phid": "PHID-XACT-DREV-3ikkbxq2mp7jdfx",
            "type": "inline",
            "authorPHID": "PHID-USER-n6m3vllhvnoqjfyh2ojn",
            "objectPHID": "PHID-DREV-uaiam7fvs5n4pshjcdpc",
            "dateCreated": 1786478303,
            "dateModified": 1786478303,
            "groupID": "3izyumt5oyefdd3vsgvl6sbwytpnx2ev",
            "comments": [
                {
                "id": 1,
                "phid": "PHID-XCMT-yw7yibp7mgodhengbghl",
                "version": 1,
                "authorPHID": "PHID-USER-n6m3vllhvnoqjfyh2ojn",
                "dateCreated": 1786478295,
                "dateModified": 1786478303,
                "removed": false,
                "content": {
                    "raw": "Inline comment!!"
                }
                }
            ],
            "fields": {
                "diff": {
                "id": 1,
                "phid": "PHID-DIFF-qtmxf3odrhikqufchso6"
                },
                "path": "src/jjpr/forges/gerrit/lib/util.py",
                "line": 40,
                "length": 1,
                "replyToCommentPHID": null,
                "isDone": false
            }
        },
        """
        for txn in txns:
            if txn["type"] == "inline" and txn["fields"]["isDone"] is False:
                counts[rev_num] = counts.get(rev_num, 0) + 1
    return counts


def check_color(status: str) -> str:
    return {
        "passed": "green",
        "failed": "red",
        "aborted": "red",
        "error": "red",
        "deadlocked": "red",
    }.get(status, "yellow")


def check_to_str(check: dict[str, t.Any]) -> str:
    status = check["status"]
    if status == "passed":
        txt = "[green]✔[/green]"
    elif status in {"failed", "aborted", "error", "deadlocked"}:
        txt = "[red]✗[/red]"
    else:
        txt = "[yellow]…[/yellow]"
    return f"[link={check['url']}]{txt}[/link]"
