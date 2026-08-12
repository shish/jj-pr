import logging
import os
from typing import Protocol

from ..utils import cr, exc, git, jj
from . import demo, gerrit, github, phabricator

log = logging.getLogger(__name__)


class ForgeModule(Protocol):
    __name__: str

    @staticmethod
    def upload_cmd(
        remote: str,
        ref: jj.RevSet | None,
        draft: bool = False,
        message: str | None = None,
        pre_commit: bool = True,
    ) -> None: ...

    @staticmethod
    def download_cmd(remote: str, identifier: str) -> None: ...

    @staticmethod
    def rebase_cmd(
        remote: str,
        change_ids: list[jj.ChangeId],
        skip_without_cr: bool = False,
    ) -> None: ...

    @staticmethod
    def list_cmd(remote: str) -> list[cr.CodeReview]: ...

    @staticmethod
    def log_cmd(remote: str, args: list[str]) -> str: ...


def _get_forge_from_env() -> str | None:
    return os.getenv("JJ_PR_FORGE")


def _get_forge_from_config() -> str | None:
    return jj.config_get("pr.forge")


def _get_forge_from_remote_name(remote: str) -> str | None:
    if remote in {"github", "phabricator", "gerrit", "demo"}:
        return remote
    return None


def _get_forge_from_remote_url(remote: str) -> str | None:
    url = git.get_remote_url(remote)
    domain = url.host.lower() if url.host else ""
    if "github.com" in domain:
        return "github"
    elif "phab" in domain:
        return "phabricator"
    elif "gerrit" in domain:
        return "gerrit"
    return None


def get_forge(remote: str) -> ForgeModule:
    forge = (
        _get_forge_from_env()
        or _get_forge_from_config()
        or _get_forge_from_remote_name(remote)
        or _get_forge_from_remote_url(remote)
    )

    if forge == "github":
        return github
    elif forge == "phabricator":
        return phabricator
    elif forge == "gerrit":
        return gerrit
    elif forge == "demo":
        return demo
    else:
        raise exc.UserError(
            "Could not detect forge from remote URL. "
            "Please use `jj config set --repo pr.forge {github,phabricator,gerrit,demo}`."
        )
