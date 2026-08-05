import logging
import re

from ...utils import exec, git, jj
from .lib import info

log = logging.getLogger(__name__)


def upload_cmd(
    remote: str,
    ref: str | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    forge_info = info.get_forge_info(remote)
    changes = jj.change_id(ref) if ref else jj.pushable_stack()

    # if a change in the stack has a branch name that starts with "pr/":
    branches = [jj.branches_pointing_to(change, prefix="pr/") for change in changes]
    branches = [list(b)[0] for b in branches if b]
    if branches:
        # - advance that branch to the current change
        # - force-push the branch to the remote
        pr_branch = branches[-1]
        log.info(f"Updating existing PR branch: {pr_branch}")
        with jj.with_new(changes[-1]):
            jj.bookmark_advance(pr_branch, to=changes[-1])
            jj.git_push(remote=forge_info.remote, bookmark=pr_branch)
    else:
        # - create a new branch named "pr/<sanitized-title>" where
        #   <sanitized-title> is a name based on the description of
        #   the last change in the stack
        # - push that branch to the remote
        # - create a PR on GitHub with the new branch as the source
        #   and the merge target as the destination
        description = jj.description_of(changes[-1])
        if not description:
            raise ValueError(f"No description found for change {changes[-1]}")
        title = description.splitlines()[0]
        sanitized_title = re.sub(r"[^a-zA-Z0-9\-]+", "-", title).strip("-").lower()
        pr_branch = git.unique_branch_name(f"pr/{sanitized_title}")
        log.info(f"Creating new PR branch: {pr_branch}")
        with jj.with_new(changes[-1]):
            jj.bookmark_create(pr_branch, r=changes[-1])
            jj.git_push(remote=forge_info.remote, bookmark=pr_branch)
            base = git.get_merge_target()
            args = [
                "gh",
                "pr",
                "create",
                "--fill",
                "--head",
                pr_branch,
                "--base",
                base,
            ]
            if draft:
                args.append("--draft")
            if message:
                args.extend(["-b", message])
            exec.run(*args)
