import logging
from typing import Optional
from urllib.parse import urlparse

from .. import utils
from .base import Forge
from .gerrit import Gerrit
from .github import GitHub
from .phabricator import Phabricator

log = logging.getLogger(__name__)


def detect_forge_from_url(url: str) -> Optional[str]:
    if not url:
        return None

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove 'www.' prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    if "github.com" in domain:
        return "github"
    elif "phabricator" in domain:
        return "phabricator"
    elif "gerrit" in domain:
        return "gerrit"

    return None


def get_forge(forge: Optional[str], remote: str) -> Optional[Forge]:
    remote_url = utils.get_git_remote_url(remote)
    if not remote_url:
        log.error(f"Error: Could not find git remote URL for '{remote}'")
        return None

    # If forge is explicitly specified, use that
    if not forge:
        forge = detect_forge_from_url(remote_url)
        if not forge:
            log.error(
                f"Error: Could not detect forge from remote URL: {remote_url}. "
                "Please specify --forge explicitly (github, phabricator, gerrit)."
            )
            return None

    if forge == "github":
        return GitHub(remote, remote_url)
    elif forge == "phabricator":
        return Phabricator(remote, remote_url)
    elif forge == "gerrit":
        return Gerrit(remote, remote_url)

    return None  # pragma: no cover


__all__ = [
    "Forge",
    "GitHub",
    "Phabricator",
    "Gerrit",
    "get_forge",
]
