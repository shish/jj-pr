import logging
from abc import ABC, abstractmethod

from ..utils import git
from .cr import CodeReview

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

    def asdict(self) -> dict:
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
    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        """Push changes to the forge."""

    @abstractmethod
    def checkout_cr(self, identifier: str) -> None:
        """Checkout changes from the forge."""

    @abstractmethod
    def list_crs(self, all_projects: bool = False) -> list[CodeReview]:
        """List items on the forge, returning a list of CRListItem objects."""
