import re
import typing as t

import httpx

from ....utils import git, jj
from ...base import ForgeInfo
from .client import GerritClient


@t.final
class GerritInfo(ForgeInfo[GerritClient]):
    def __init__(self, remote: str):
        super().__init__(remote)

        if conf := jj.config_get("gerrit.review-url"):
            self.forge_url = httpx.URL(conf)
        else:
            if self.remote_url.scheme in {"http", "https"}:
                self.forge_url = self.remote_url.copy_with(path=None)
            else:
                self.forge_url = self.remote_url.copy_with(
                    scheme="https", username=None, port=None, path=None
                )

        if match := re.match(r"^/(a/)?(.*?)(\.git)?$", self.remote_url.path):
            self.project_id = match.group(2)
        else:
            raise ValueError(
                f"Invalid Gerrit remote URL format: {self.remote_url}. Expected format: /project/path"
            )

        if drb := jj.config_get("gerrit.default-remote-branch"):
            self.default_merge_target = drb
        else:
            self.default_merge_target = git.get_merge_target()

        self.client = GerritClient(self.forge_url)


def get_forge_info(remote: str) -> GerritInfo:
    return GerritInfo(remote)
