import re
import typing as t

from ...utils import git
from ..base import ForgeInfo
from ._client import GitHubClient


def get_forge_info(remote: str) -> ForgeInfo[GitHubClient]:
    f = ForgeInfo[GitHubClient](remote)

    if f.remote_url.scheme in {"http", "https"}:
        f.forge_url = f.remote_url.copy_with(path=None)
    else:
        f.forge_url = f.remote_url.copy_with(
            scheme="https", username=None, port=None, path=None
        )
    f.client = GitHubClient(f.forge_url)

    if match := re.match("^/([^/]+?/[^/]+?)(\\.git)?$", f.remote_url.path):
        f.project_id = match.group(1)
    else:
        raise ValueError(
            f"Invalid GitHub remote URL format: {f.remote_url}. Expected format: owner/repo"
        )

    repo_info = _get_repo_info(f.client, f.project_id)
    f.default_merge_target = (
        repo_info["defaultBranchRef"]["name"] or git.get_merge_target()
    )

    return f


def _get_repo_info(client: GitHubClient, project_id: str) -> dict[str, t.Any]:
    query = """
      fragment repo on Repository {
        id
        name
        owner { login }
        viewerPermission
        defaultBranchRef {
          name
        }
        isPrivate
      }
      query RepositoryNetwork($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          ...repo
          parent {
            ...repo
          }
        }
      }
    """
    owner, name = project_id.split("/")
    variables = {
        "owner": owner,
        "name": name,
    }
    return client.graphql(query, variables)["repository"]
