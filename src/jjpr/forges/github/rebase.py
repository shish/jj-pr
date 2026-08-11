import logging
import typing as t

from ...utils import jj
from .lib import client, info

log = logging.getLogger(__name__)


def _get_descendants_bookmarks(root: jj.ChangeId) -> list[str]:
    """
    Find all bookmarks on any descendant commits of `root`.
    Returns a list of bookmark names (with @remote suffix if remote).
    """
    output = jj.run(
        "log",
        "-r",
        f"{root}::",
        "--no-graph",
        "-T",
        'bookmarks.map(|b| b.name()).join("\n") ++ "\n"',
        cap=True,
    )
    bookmarks = [b.strip() for b in output.split("\n") if b.strip()]
    return bookmarks


def _find_pr_base_for_stack(
    client: client.GitHubClient, owner: str, name: str, bookmarks: list[str]
) -> str | None:
    """
    Given a list of bookmarks from descendant commits, extract branch names and query
    for the corresponding open PRs to find their baseRefName (merge target).
    Returns the baseRefName if found, else None.
    """
    if not bookmarks:
        return None

    # Collect all unique branch names from bookmarks
    branches_set: set[str] = set()
    for bm in bookmarks:
        # Strip @remote suffix and * (conflicted) marker
        branch = bm.removesuffix("*").split("@", 1)[0]
        if branch:
            branches_set.add(branch)

    branches = sorted(branches_set)
    if not branches:
        return None

    # Query for the PRs with those head branches
    aliases = [f"b{i}" for i in range(len(branches))]
    args = ", ".join(f"${a}: String!" for a in aliases)
    pr_field = "baseRefName"
    selections = "\n".join(
        f"{a}: pullRequests(headRefName: ${a}, states: [OPEN], first: 1) {{"
        f" nodes {{ {pr_field} }} }}"
        for a in aliases
    )
    query = f"""
      query PullRequestBaseRefs($owner: String!, $name: String!, {args}) {{
        repository(owner: $owner, name: $name) {{
          {selections}
        }}
      }}
    """
    variables: dict[str, t.Any] = {"owner": owner, "name": name}
    variables.update(zip(aliases, branches))

    data = client.graphql(query, variables)["repository"]
    for a in aliases:
        prs = data[a]["nodes"]
        if prs:
            return prs[0][pr_field]

    return None


def rebase_cmd(remote: str, change_ids: list[jj.ChangeId]) -> None:
    forge_info = info.get_forge_info(remote)
    jj.git_fetch(all_remotes=True)

    owner, name = forge_info.project_id.split("/")

    for root in change_ids:
        # Check if any descendant of this root has a PR
        bookmarks = _get_descendants_bookmarks(root)

        # Try to find the merge target from the PR
        merge_target = _find_pr_base_for_stack(
            forge_info.client, owner, name, bookmarks
        )

        # If we found a merge target, use it; otherwise fall back to default
        if merge_target:
            base = jj.revset(f"{merge_target}@{forge_info.remote}")
            log.info(
                f"Found PR merge target '{merge_target}' for {root}, "
                f"rebasing descendants onto {base}"
            )
        else:
            base = jj.revset(f"{forge_info.default_merge_target}@{forge_info.remote}")
            log.info(
                f"No PR found for descendants of {root}, "
                f"rebasing onto default target {base}"
            )

        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)
