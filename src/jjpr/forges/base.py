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
    _client: TClient | None = field(default=None, init=False)

    def __post_init__(self):
        self.remote_url = git.get_remote_url(self.remote)
        self.forge_url = self.remote_url

    @property
    def client(self) -> TClient:
        if self._client is None:
            raise ValueError("Client not set")
        return self._client

    @client.setter
    def client(self, value: TClient):
        self._client = value
