import logging

from ...utils import jj
from ._info import get_forge_info

log = logging.getLogger(__name__)


def upload_cmd(
    remote: str,
    ref: str | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    f = get_forge_info(remote)
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
        remote_branch=f.default_merge_target,
    )
