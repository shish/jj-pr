import logging

from ...utils import jj
from .lib import info

log = logging.getLogger(__name__)


def rebase_cmd(
    remote: str,
    change_ids: list[jj.ChangeId],
    skip_without_cr: bool = False,
) -> None:
    forge_info = info.get_forge_info(remote)
    for root in change_ids:
        base = jj.revset(f"{forge_info.default_merge_target}@{remote}")
        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)
