import re
import typing as t

from ...utils import jj, text
from ._info import get_forge_info
from ._util import colour_state, get_checks


def log_cmd(remote: str, args: list[str]) -> str:
    f = get_forge_info(remote)

    def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
        id_to_state: dict[str, str] = {}
        # Fetch "my open reviews and their status" from gerrit,
        # index them by change ID. FIXME: "my open reviews" is
        # a poor approxmation of "the changes visible in jj log"
        query = f"owner:self+status:open+project:{f.project_id}"
        changes_response = f.client.get(
            f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
        ).json()
        for change in changes_response:
            blockers = []
            for req in change.get("submit_requirements", []):
                if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}:
                    req_name = re.sub("[^A-Z]+", "", req["name"])
                    blockers.append(req_name)
            state = colour_state(
                is_private=change.get("is_private", False),
                work_in_progress=change.get("work_in_progress", False),
                blockers=len(blockers) > 0,
                url=f.forge_url.join(f"/c/{change['_number']}"),
            )
            checks = get_checks(f.client, change["_number"])
            id_to_state[str(change["change_id"])] = text.rich_str(
                state, *[_check_to_str(check) for check in checks]
            )
        return id_to_state

    return jj.log_with_annotations(
        args,
        '"I" ++ commit.change_id().normal_hex() ++"6a6a6964"',
        _pr_ids_to_states,
    )


def _check_to_str(check: dict[str, t.Any]) -> str:
    state = check.get("state")
    if state in {"SUCCESSFUL", "NOT_RELEVANT"}:
        txt = "[green]✔[/green]"
    elif state == "FAILED":
        txt = "[red]✗[/red]"
    else:
        txt = "[yellow]…[/yellow]"
    if url := check.get("url"):
        return f"[link={url}]{txt}[/link]"
    return txt
