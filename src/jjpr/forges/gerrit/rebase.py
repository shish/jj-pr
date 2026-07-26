from ...utils import jj
from ._info import get_forge_info


def rebase_cmd(remote: str, change_ids: list[jj.ChangeID]) -> None:
    f = get_forge_info(remote)
    jj.git_fetch(all_remotes=True)
    for root in change_ids:
        base = f"{f.default_merge_target}@{f.remote}"
        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)
