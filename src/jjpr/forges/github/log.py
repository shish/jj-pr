import typing as t

import httpx

from ...utils import cr, jj, text
from ._client import GitHubClient
from ._info import get_forge_info
from . import _util

_PR_FIELDS = f"""
  url
  isDraft
  headRefName
  {_util.STATUS_CHECK_FIELDS}
  {_util.REVIEW_FIELDS}
"""


def _branch_names(pr_ids: list[str]) -> list[str]:
    """Strip the `*` (conflicted bookmark) and `@remote` suffixes that
    `commit.bookmarks()` may add, to recover the underlying branch names."""
    names: set[str] = set()
    for pr_id in pr_ids:
        name = pr_id.removesuffix("*").split("@", 1)[0]
        if name:
            names.add(name)
    return sorted(names)


def _get_prs_by_branch(
    client: GitHubClient, owner: str, name: str, branches: list[str]
) -> list[dict[str, t.Any]]:
    if not branches:
        return []

    aliases = [f"b{i}" for i in range(len(branches))]
    args = ", ".join(f"${a}: String!" for a in aliases)
    selections = "\n".join(
        f"{a}: pullRequests(headRefName: ${a}, states: [OPEN], first: 1) {{"
        f" nodes {{ {_PR_FIELDS} }} }}"
        for a in aliases
    )
    query = f"""
      query PullRequestsByBranch($owner: String!, $name: String!, {args}) {{
        repository(owner: $owner, name: $name) {{
          {selections}
        }}
      }}
    """
    variables: dict[str, t.Any] = {"owner": owner, "name": name}
    variables.update(zip(aliases, branches))

    data = client.graphql(query, variables)["repository"]
    prs: list[dict[str, t.Any]] = []
    for a in aliases:
        prs.extend(data[a]["nodes"])
    return prs


def log_cmd(remote: str, args: list[str]) -> str:
    f = get_forge_info(remote)

    def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
        id_to_state: dict[str, str] = {}
        owner, name = f.project_id.split("/")
        prs = _get_prs_by_branch(f.client, owner, name, _branch_names(pr_ids))

        for pr in prs:
            state = text.rich_str(
                _util.pr2state(pr),
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
                    for check in _util.flatten_checks(pr)
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
