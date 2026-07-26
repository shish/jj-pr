import logging
import typing as t

from ...utils import jj
from ._client import GitHubClient
from ._info import get_forge_info

log = logging.getLogger(__name__)


def download_cmd(remote: str, identifier: str) -> None:
    f = get_forge_info(remote)
    # GH_DEBUG=api gh pr checkout 13
    log.info(f"Downloading PR {identifier} from {f.remote_url}")
    owner, name = f.project_id.split("/")
    pr_info = _get_pr_info(f.client, owner, name, int(identifier.lstrip("#")))
    branch_name = pr_info["headRefName"]
    jj.git_fetch(remote=f.remote)
    jj.bookmark_track(branch_name, remote=f.remote)
    jj.new(f"{branch_name}@{f.remote}")


def _get_pr_info(
    client: GitHubClient, owner: str, name: str, pr_number: int
) -> dict[str, t.Any]:
    query = """
      query GetPullRequest($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
          pullRequest(number: $number) {
            headRefName
            baseRefName
            title
            body
            state
            headRepository {
              id
              name
            }
            headRepositoryOwner {
              id
              login
              ...on User {name}
            }
            isCrossRepository
            maintainerCanModify
            id
          }
        }
      }
    """
    variables = {
        "owner": owner,
        "name": name,
        "number": pr_number,
    }
    return client.graphql(query, variables)["repository"]["pullRequest"]
