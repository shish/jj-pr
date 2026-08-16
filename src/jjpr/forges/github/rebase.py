import logging

from ...utils import jj
from .lib import client, info

log = logging.getLogger(__name__)


def _find_pr_base_for_root(
    forge_info: info.GitHubInfo, owner: str, name: str, change_id: jj.ChangeId
) -> str | None:
    """
    Given a list of bookmarks from descendant commits, extract branch names and query
    for the corresponding open PRs to find their baseRefName (merge target).
    Returns the baseRefName if found, else None.
    """
    query = """
      query PullRequestBaseRefs($owner: String!, $name: String!, $headRefName: String!) {
        repository(owner: $owner, name: $name) {
          pullRequests(headRefName: $headRefName, first: 1) {
            nodes { baseRefName }
          }
        }
      }
    """
    variables: client.GqlVars = {
        "owner": owner,
        "name": name,
        "headRefName": jj.change_to_push_bookmark(change_id),
    }

    repo = forge_info.client.graphql(query, variables)["repository"]
    prs = repo["pullRequests"]["nodes"]
    if prs:
        return prs[0]["baseRefName"]
    return None


def rebase_cmd(
    remote: str,
    change_ids: list[jj.ChangeId],
    skip_without_cr: bool = False,
) -> None:
    forge_info = info.get_forge_info(remote)
    owner, name = forge_info.project_id.split("/")

    for root in change_ids:
        # Try to find the merge target from the PR
        merge_target = _find_pr_base_for_root(forge_info, owner, name, root)

        # If we found a merge target, use it; otherwise fall back to default (or skip)
        if merge_target:
            base = jj.revset(f"{merge_target}@{forge_info.remote}")
            log.info(
                f"Found PR merge target '{merge_target}' for {root}, "
                f"rebasing descendants onto {base}"
            )
        elif skip_without_cr:
            log.info(f"No PR found for descendants of {root}, skipping")
            continue
        else:
            base = jj.revset(f"{forge_info.default_merge_target}@{forge_info.remote}")
            log.info(
                f"No PR found for descendants of {root}, "
                f"rebasing onto default target {base}"
            )

        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)
