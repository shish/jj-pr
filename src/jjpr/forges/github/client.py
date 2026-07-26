import os
import typing as t
import logging
import json

import httpx

from ...utils import exc, netrc

log = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, base_url: httpx.URL):
        if base_url.host == "github.com":
            base_url = httpx.URL("https://api.github.com")
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
    def _resolve_token(base_url: httpx.URL) -> str:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            return token

        host = base_url.host
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

    def graphql(self, query: str, variables: dict[str, str] | None = None):
        data: dict[str, t.Any] = {"query": query}
        if variables:
            data["variables"] = variables
        response = self.client.post("/graphql", json=data)
        response.raise_for_status()
        data = response.json()["data"]

        # fmt: off
        log.debug(
            f"API call: /graphql\n"
            f"  == {query}\n"
            f"  <- {json.dumps(variables)}\n"
            f"  -> {json.dumps(data)}"
        )
        # fmt: on

        return data
