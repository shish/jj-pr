import json

import httpx

from ...utils import cr, exec, jj, text
from ._info import get_forge_info
from ._util import colour_state


def log_cmd(remote: str, args: list[str]) -> str:
    f = get_forge_info(remote)

    def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
        id_to_state: dict[str, str] = {}
        # TODO: "all open PRs" is a poor approxmation of "The PRs listed in $pr_ids"
        prs = json.loads(
            exec.run(
                "gh",
                "pr",
                "list",
                "--repo",
                str(f.remote_url),
                "--json",
                "url,isDraft,reviews,headRefName,statusCheckRollup",
            )
        )
        for pr in prs:
            state = text.rich_str(
                colour_state(
                    is_draft=pr.get("isDraft", False),
                    reviews=pr.get("reviews", []),
                    url=httpx.URL(pr["url"]),
                ),
                *[
                    cr.Blocker(
                        name={
                            "SUCCESS": "✔",
                            "FAILURE": "✗",
                            "PENDING": "…",
                        }.get(check["conclusion"], f"<{check['conclusion']}>"),
                        color={
                            "SUCCESS": "green",
                            "FAILURE": "red",
                            "PENDING": "yellow",
                        }.get(check["conclusion"], "normal"),
                        url=httpx.URL(check["detailsUrl"]),
                    )
                    for check in pr.get("statusCheckRollup", [])
                ],
            )
            id_to_state[pr["headRefName"]] = state
            id_to_state[pr["headRefName"] + "*"] = state
            id_to_state[pr["headRefName"] + "@" + f.remote] = state
        return id_to_state

    return jj.log_with_annotations(
        args,
        'commit.bookmarks().join(",")',
        _pr_ids_to_states,
    )
