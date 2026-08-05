import re

import httpx

from ....utils import git, jj
from ...base import ForgeInfo
from .client import GerritClient


def get_forge_info(remote: str) -> ForgeInfo[GerritClient]:
    f = ForgeInfo[GerritClient](remote)

    if conf := jj.config_get("gerrit.review-url"):
        f.forge_url = httpx.URL(conf)
    else:
        if f.remote_url.scheme in {"http", "https"}:
            f.forge_url = f.remote_url.copy_with(path=None)
        else:
            f.forge_url = f.remote_url.copy_with(
                scheme="https", username=None, port=None, path=None
            )

    if match := re.match(r"^/(a/)?(.*?)(\.git)?$", f.remote_url.path):
        f.project_id = match.group(2)

    if drb := jj.config_get("gerrit.default-remote-branch"):
        f.default_merge_target = drb
    else:
        f.default_merge_target = git.get_merge_target()

    f.client = GerritClient(f.forge_url)

    return f
