import os

import httpx

from ...utils import exc, netrc


class GitHubClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = self._resolve_token(base_url)
        # Set the token in the environment for use by gh CLI
        os.environ["GITHUB_TOKEN"] = self.token
        self.client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

    @staticmethod
    def _resolve_token(base_url: str) -> str:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            return token

        host = httpx.URL(base_url).host
        auth = netrc.read(host)
        if auth:
            return auth[1]

        raise exc.UserError(
            "Could not find a GitHub token. Set the GITHUB_TOKEN or GH_TOKEN "
            f"environment variable, or add credentials for {host} to ~/.netrc"
        )

    def get(self):
        pass

    def post(self, name: str):
        pass

    def graphql(self):
        pass
