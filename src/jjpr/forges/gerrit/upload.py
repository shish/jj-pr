import logging

from ...utils import jj
from .lib import info

log = logging.getLogger(__name__)


def upload_cmd(
    remote: str,
    ref: jj.RevSet | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    forge_info = info.get_forge_info(remote)
    if ref:
        change_id = jj.change_id(ref)
        range = f"{change_id}::{change_id}"
    else:
        range = jj.closest_work()
    log.info(f"Pushing {range} to gerrit")
    jj.gerrit_upload(
        r=range,
        wip=draft,
        message=message,
        remote_branch=forge_info.default_merge_target,
    )
