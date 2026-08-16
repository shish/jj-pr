import logging

import httpx

from ...utils import jj
from .lib import info

log = logging.getLogger(__name__)

_REVERSE_HEX_TO_NORMAL_HEX = str.maketrans(
    "zyxwvutsrqponmlk",
    "0123456789abcdef",
)


def rebase_cmd(
    remote: str,
    change_ids: list[jj.ChangeId],
    skip_without_cr: bool = False,
) -> None:
    forge_info = info.get_forge_info(remote)
    jj.git_fetch(all_remotes=True)
    for root in change_ids:
        if branch := _get_gerrit_branch(forge_info, root, remote):
            base = jj.revset(branch)
            log.info(f"Found CR branch '{branch}' for {root}, rebasing onto {base}")
        elif skip_without_cr:
            log.info(f"No CR found for {root}, skipping")
            continue
        else:
            base = jj.revset(f"{forge_info.default_merge_target}@{forge_info.remote}")
            log.info(f"No CR found for {root}, rebasing onto default target {base}")
        print(f"Rebasing {root} onto {base}")
        jj.rebase(d=base, s=root)


def _get_gerrit_branch(
    forge_info: info.GerritInfo, root: jj.ChangeId, remote: str
) -> str | None:
    """Return '{branch}@{remote}' for the given Gerrit Change-Id, or None if not found."""
    try:
        gid = "I" + root.translate(_REVERSE_HEX_TO_NORMAL_HEX) + "6a6a6964"
        change_data = forge_info.client.get(f"changes/{gid}").json()
    except httpx.HTTPStatusError:
        return None
    branch = change_data.get("branch")
    if not branch:
        return None
    return f"{branch}@{remote}"
