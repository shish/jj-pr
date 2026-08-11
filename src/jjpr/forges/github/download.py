import logging
import typing as t

from ...utils import jj
from .lib import client, info

log = logging.getLogger(__name__)


def download_cmd(remote: str, identifier: str) -> None:
    forge_info = info.get_forge_info(remote)
    # GH_DEBUG=api gh pr checkout 13
    log.info(f"Downloading PR {identifier} from {forge_info.remote_url}")
    owner, name = forge_info.project_id.split("/")
    pr_info = _get_pr_info(forge_info.client, owner, name, int(identifier.lstrip("#")))
    branch_name = pr_info["headRefName"]
    jj.git_fetch(remote=forge_info.remote)
    jj.bookmark_track(branch_name, remote=forge_info.remote)
    jj.new(jj.revset(f"{branch_name}@{forge_info.remote}"))


def _get_pr_info(
    client: client.GitHubClient, owner: str, name: str, pr_number: int
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
