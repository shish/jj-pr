import typing as t

import httpx

from ...utils import cr
from ._client import PhabricatorClient

PhID = str


def callsign_to_phid(client: PhabricatorClient, callsign: str) -> PhID:
    return client.call(
        "diffusion.repository.search",
        constraints={"callsigns": [callsign]},
    )["data"][0]["phid"]


def get_checks(
    client: PhabricatorClient, forge_url: httpx.URL, diff_phids: list[PhID]
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
                "url": forge_url.join(f"/harbormaster/build/{build['id']}/"),
            }
        )
    return checks


def colour_state(state: str, url: httpx.URL) -> cr.State:
    c = {
        "Draft": "cyan",
        "Changes Planned": "cyan",
        "Rejected": "red",
        "Needs Review": "yellow",
        "Accepted": "green",
        "Closed": "grey",
        "Abandoned": "grey",
    }.get(state, "yellow")
    return cr.State(state, color=c, url=url)


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
