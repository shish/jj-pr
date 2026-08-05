import logging

import httpx

from ...utils import jj, text
from .lib import info, util
from .list import _get_checks

log = logging.getLogger(__name__)


def log_cmd(remote: str, args: list[str]) -> str:
    forge_info = info.get_forge_info(remote)

    def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
        revs = forge_info.client.call(
            "differential.revision.search",
            constraints={"ids": [int(x[1:]) for x in pr_ids]},
        )["data"]
        checks_by_diff = _get_checks(
            forge_info, [rev["fields"]["diffPHID"] for rev in revs]
        )
        id_to_state: dict[str, str] = {}
        for rev in revs:
            state = util.colour_state(
                state=rev["fields"]["status"]["name"],
                url=httpx.URL(rev["fields"]["uri"]),
            )
            checks = checks_by_diff.get(rev["fields"]["diffPHID"], [])
            id_to_state[f"D{rev['id']}"] = text.rich_str(
                state, *[util.check_to_str(check) for check in checks]
            )
        return id_to_state

    return jj.log_with_annotations(
        args,
        """
        commit.description()
            .lines()
            .filter(|line| line.starts_with("Differential Revision: "))
            .map(|line| line.match(regex:"D[0-9]+"))
            .join(",")
        """,
        _pr_ids_to_states,
    )
