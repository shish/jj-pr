import re
import typing as t

from ....utils import git
from ...base import ForgeInfo
from . import client


@t.final
class GitHubInfo(ForgeInfo[client.GitHubClient]):
    def __init__(self, remote: str):
        super().__init__(remote)

        if self.remote_url.scheme in {"http", "https"}:
            self.forge_url = self.remote_url.copy_with(path=None)
        else:
            self.forge_url = self.remote_url.copy_with(
                scheme="https", username=None, port=None, path=None
            )
        self.client = client.GitHubClient(self.forge_url)

        if match := re.match("^/([^/]+?/[^/]+?)(\\.git)?$", self.remote_url.path):
            self.project_id = match.group(1)
        else:
            raise ValueError(
                f"Invalid GitHub remote URL format: {self.remote_url}. Expected format: owner/repo"
            )

        repo_info = _get_repo_info(self.client, self.project_id)
        self.repo_id = repo_info["id"]
        self.repo_owner = repo_info["owner"]["login"]
        self.repo_name = repo_info["name"]
        self.default_merge_target = (
            repo_info["defaultBranchRef"]["name"] or git.get_merge_target()
        )


def get_forge_info(remote: str) -> GitHubInfo:
    return GitHubInfo(remote)


def _get_repo_info(client: client.GitHubClient, project_id: str) -> client.RepoJson:
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
