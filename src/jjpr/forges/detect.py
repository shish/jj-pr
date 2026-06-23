import logging

from .. import exc
from ..utils import git, jj
from .base import Forge
from .gerrit.forge import Gerrit
from .github.forge import GitHub
from .phabricator.forge import Phabricator

log = logging.getLogger(__name__)


def _get_forge_from_config() -> str | None:
    return jj.config_get("pr.forge")


def _get_forge_from_remote_name(remote: str) -> str | None:
    if remote in {"github", "phabricator", "gerrit"}:
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


def get_forge(remote: str) -> Forge:
    forge = (
        _get_forge_from_config()
        or _get_forge_from_remote_name(remote)
        or _get_forge_from_remote_url(remote)
    )

    if forge == "github":
        return GitHub(remote)
    elif forge == "phabricator":
        return Phabricator(remote)
    elif forge == "gerrit":
        return Gerrit(remote)
    else:
        raise exc.UserError(
            "Could not detect forge from remote URL. "
            "Please use `jj config set --repo pr.forge {github,phabricator,gerrit}`."
        )
