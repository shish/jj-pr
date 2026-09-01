import json
import logging
import os
import typing as t
from pathlib import Path

import httpx

from ....utils import exc, netrc

PrNum = t.NewType("PrNum", int)
PrJson = t.NewType("PrJson", dict[str, t.Any])
RepoJson = t.NewType("RepoJson", dict[str, t.Any])
GqlVars = dict[str, t.Any]
log = logging.getLogger(__name__)


@t.final
class GitHubClient:
    def __init__(self, base_url: httpx.URL):
        self.base_url = base_url
        self.token = self._resolve_token(base_url)
        if base_url.host == "github.com":
            self.api_url = httpx.URL("https://api.github.com")
        else:
            self.api_url = base_url
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
            log.debug("Got token from env var")
            return token

        host = base_url.host
        auth = netrc.read(host)
        if auth:
            log.debug(f"Got token from ~/.netrc for {host}")
            return auth[1]

        try:
            token = _read_gh_hosts(host)
            if token:
                return token
        except OSError:
            pass

        raise exc.UserError(
            "Could not find a GitHub token. Set the GITHUB_TOKEN or GH_TOKEN "
            f"environment variable, add credentials for {host} to ~/.netrc, "
            "or authenticate with the gh CLI (`gh auth login`)"
        )

    def graphql(self, query: str, variables: GqlVars):
        data: dict[str, t.Any] = {"query": query}
        if variables:
            data["variables"] = variables
        response = self.client.post("/graphql", json=data)
        response.raise_for_status()
        js = response.json()
        if "errors" in js:
            raise exc.UserError(
                f"GraphQL query failed: {json.dumps(js['errors'], indent=2)}"
            )
        data = js["data"]

        # fmt: off
        log.debug(
            f"API call: /graphql\n"
            f"  == {query}\n"
            f"  <- {json.dumps(variables)}\n"
            f"  -> {json.dumps(data)}"
        )
        # fmt: on

        return data


def _read_gh_hosts(host: str) -> str | None:
    """
    hosts.yml appears to be consistently trivial, so let's parse it
    manually rather than adding a dependency on PyYAML or the gh cli
    """
    hosts_file = Path.home() / ".config" / "gh" / "hosts.yml"
    current_host: str | None = None
    for line in hosts_file.read_text().splitlines():
        # Top-level (unindented) keys are hostnames
        if line and not line[0].isspace():
            current_host = line.rstrip().removesuffix(":")
        elif current_host == host:
            key, _, value = line.strip().partition(":")
            if key == "oauth_token" and (token := value.strip()):
                return token
    return None
