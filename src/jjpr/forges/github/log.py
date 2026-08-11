import typing as t

from ...utils import cr, jj
from .lib import client, info, util

_PR_FIELDS = f"""
  url
  number
  title
  isDraft
  headRefName
  {util.STATUS_CHECK_FIELDS}
  {util.REVIEW_FIELDS}
  {util.REVIEW_THREAD_FIELDS}
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
    client: client.GitHubClient, owner: str, name: str, branches: list[str]
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
    forge_info = info.get_forge_info(remote)

    def _pr_ids_to_crs(pr_ids: list[str]) -> dict[str, cr.CodeReview]:
        owner, name = forge_info.project_id.split("/")
        prs = _get_prs_by_branch(forge_info.client, owner, name, _branch_names(pr_ids))
        return {pr["headRefName"]: util.parse_cr(pr) for pr in prs}

    return jj.log_with_annotations(
        args,
        'commit.bookmarks().map(|b| b.name()).join(",")',
        _pr_ids_to_crs,
    )
