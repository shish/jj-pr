import json
import logging
import typing as t
from pathlib import Path

import httpx

from ....utils import git
from ...base import ForgeInfo
from .client import PhabricatorClient

log = logging.getLogger(__name__)


@t.final
class PhabricatorInfo(ForgeInfo[PhabricatorClient]):
    def __init__(self, remote: str):
        super().__init__(remote)

        config_path = Path(".arcconfig")
        if config_path.exists():
            repo_config = json.loads(config_path.read_text())
        else:
            repo_config = {}

        if uri := repo_config.get("phabricator.uri"):
            self.forge_url = httpx.URL(uri)
        else:
            self.forge_url = self.remote_url.copy_with(path=None)
        self.client = PhabricatorClient(self.forge_url)

        if callsign := repo_config.get("repository.callsign"):
            self.project_id = callsign
        else:
            repos = self.client.call(
                "diffusion.repository.search",
                constraints={"uris": [str(self.remote_url)]},
            )["data"]
            if not repos:
                raise ValueError(
                    f"Could not find a Phabricator repository for {self.remote_url}"
                )
            self.project_id = repos[0]["fields"]["callsign"]

        if merge_target := repo_config.get("arc.land.onto.default"):
            self.default_merge_target = merge_target
        else:
            self.default_merge_target = git.get_merge_target()

        # fmt: off
        log.info(
            f"Phabricator settings:\n"
            f"  forge_url: {self.forge_url}\n"
            f"  project_id: {self.project_id}\n"
            f"  default_merge_target: {self.default_merge_target}"
        )
        # fmt: on


def get_forge_info(remote: str) -> PhabricatorInfo:
    return PhabricatorInfo(remote)
