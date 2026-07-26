import logging

from ...utils import jj
from ._info import get_forge_info

log = logging.getLogger(__name__)


def rebase_cmd(remote: str, change_ids: list[jj.ChangeID]) -> None:
    info = get_forge_info(remote)
    jj.git_fetch(all_remotes=True)
    for root in change_ids:
        base = f"{info.default_merge_target}@{remote}"
        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)
