import logging
from abc import ABC, abstractmethod

from ..utils import git
from . import cr

log = logging.getLogger(__name__)


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str) -> None:
        self.remote = remote
        self.remote_url = git.get_remote_url(remote)
        self.forge_url = self.remote_url
        self.project_id = "unknown"

    def asdict(self) -> dict[str, str]:
        return {
            "name": self.__class__.__name__,
            "remote": self.remote,
            "remote_url": str(self.remote_url),
            "forge_url": str(self.forge_url),
            "project_id": self.project_id,
        }

    def __rich__(self) -> str:
        return f"[link={self.forge_url}]{self.__class__.__name__}[/link]"

    @abstractmethod
    def upload_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
        pre_commit: bool = True,
    ) -> None:
        """Upload changes to the forge."""

    @abstractmethod
    def download_cr(self, identifier: str) -> None:
        """Download changes from the forge."""

    @abstractmethod
    def list_crs(self) -> list[cr.CodeReview]:
        """List open CRs for this project, returning a list of CRListItem objects."""

    @abstractmethod
    def log(self, args: list[str]) -> str:
        """Run `jj log` with annotated extra output for the forge."""
