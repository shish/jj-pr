import logging
import typing as t
from dataclasses import dataclass, field

import httpx

from ..utils import git

log = logging.getLogger(__name__)

TClient = t.TypeVar("TClient")


@dataclass
class ForgeInfo(t.Generic[TClient]):
    remote: str
    remote_url: httpx.URL = field(init=False)
    forge_url: httpx.URL = field(init=False)
    project_id: str = field(default="unknown")
    default_merge_target: str | None = field(default=None)
    client: TClient = field(default=None)  # type: ignore

    def __post_init__(self):
        self.remote_url = git.get_remote_url(self.remote)
        self.forge_url = self.remote_url
