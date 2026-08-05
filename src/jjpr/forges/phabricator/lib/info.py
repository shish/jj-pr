import json
import logging
from pathlib import Path

import httpx

from ....utils import git
from ...base import ForgeInfo
from .client import PhabricatorClient

log = logging.getLogger(__name__)


def get_forge_info(remote: str) -> ForgeInfo[PhabricatorClient]:
    f = ForgeInfo[PhabricatorClient](remote)

    config_path = Path(".arcconfig")
    if config_path.exists():
        repo_config = json.loads(config_path.read_text())
    else:
        repo_config = {}

    if uri := repo_config.get("phabricator.uri"):
        f.forge_url = httpx.URL(uri)
    else:
        f.forge_url = f.remote_url.copy_with(path=None)
    f.client = PhabricatorClient(f.forge_url)

    if callsign := repo_config.get("repository.callsign"):
        f.project_id = callsign
    else:
        f.project_id = f.client.call(
            "diffusion.repository.search",
            constraints={"uris": [str(f.remote_url)]},
        )["data"][0]["fields"]["callsign"]

    if merge_target := repo_config.get("arc.land.onto.default"):
        f.default_merge_target = merge_target
    else:
        f.default_merge_target = git.get_merge_target()

    # fmt: off
    log.info(
        f"Phabricator settings:\n"
        f"  forge_url: {f.forge_url}\n"
        f"  project_id: {f.project_id}\n"
        f"  default_merge_target: {f.default_merge_target}"
    )
    # fmt: on

    return f
