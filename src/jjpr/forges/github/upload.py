import logging
import typing as t

from ...utils import exec, git, jj
from .lib import client, info

log = logging.getLogger(__name__)


PR_FIELDS = """
    number
    title
    body
    state
    stack {
        id
        number
        baseRefName
    }
    headRefName
    baseRefName
    headRepository {
        id
        name
    }
    headRepositoryOwner {
        id
        login
        ...on User {name}
    }
    isCrossRepository
    maintainerCanModify
    id
"""


class UploadPr(t.TypedDict):
    id: str
    number: client.PrNum
    title: str
    body: str
    stack: dict[str, t.Any] | None
    baseRefName: str


def upload_cmd(
    remote: str,
    ref: jj.RevSet | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    """
    GitHub's implementation of stacked diffs is somewhat lacking, so
    we have a somewhat painful process...

    - It's a stack of PRs, not a stack of Changes
      - For parity with gerrit, we generate one PR per change automatically
      - Hypothetically we could have a mode where we look at branches, but
        that's messy
    - Stacks are append-only
      - No re-ordering
      - No removing PRs from a stack

    So in practice, we go through all the changes, see if any have a stack
    associated with them, delete it, then make a new stack
    """
    forge_info = info.get_forge_info(remote)
    changes = jj.change_ids(ref) if ref else jj.pushable_stack()

    # Create-or-update "change-XYZ" bookmarks for each change
    change_flags: list[str] = []
    for change_id in changes:
        change_flags.extend(["--change", change_id])
    jj.run("git", "push", *change_flags)

    # Check if any of the changes already have an open PR,
    # and those PRs are part of a stack
    change_to_existing_pr: dict[jj.ChangeId, UploadPr] = {}
    existing_stacks: list[int] = []
    for change_id in changes:
        my_branch = jj.change_to_push_bookmark(change_id)
        if existing_pr := _get_pr(forge_info, my_branch):
            if existing_pr["stack"] is not None:
                existing_stacks.append(existing_pr["stack"]["number"])
            change_to_existing_pr[change_id] = existing_pr

    # Delete any existing stacks
    # TODO: if all of the existing PRs are in the same stack,
    # in the same order, and we are only updating the
    # title/body/diff, then we don't need to re-create it
    for existing_stack in set(existing_stacks):
        exec.run("gh", "stack", "unstack", str(existing_stack))

    # Create-or-update PRs for each change
    new_stack: list[client.PrNum] = []
    for change_id in changes:
        my_branch = jj.change_to_push_bookmark(change_id)
        parent_id = jj.change_id(jj.revset(f"{change_id}-"))
        if jj.change_info(parent_id, "self.immutable()") == "true":
            base_branch = git.get_merge_target(remote)
        else:
            base_branch = jj.change_to_push_bookmark(parent_id)

        if existing_pr := change_to_existing_pr.get(change_id):
            pr = _update_pr(forge_info, change_id, existing_pr, base_branch, message)
        else:
            pr = _create_pr(forge_info, change_id, my_branch, base_branch, draft)
        new_stack.append(pr["number"])

    # Link the existing and new PRs into a stack
    if len(new_stack) > 1:
        exec.run("gh", "stack", "link", *[str(pr) for pr in new_stack])


def _get_pr(forge_info: info.GitHubInfo, head_ref: str) -> UploadPr | None:
    query = f"""
        query GetPullRequestByHeadRef($owner: String!, $name: String!, $headRef: String!, $states: [PullRequestState!]) {{
            repository(owner: $owner, name: $name) {{
                pullRequests(headRefName: $headRef, states: $states, first: 1) {{
                    nodes {{
                        {PR_FIELDS}
                    }}
                }}
            }}
        }}
    """
    variables = {
        "owner": forge_info.repo_owner,
        "name": forge_info.repo_name,
        "headRef": head_ref,
        "states": ["OPEN"],
    }
    result = forge_info.client.graphql(query, variables)
    pr_nodes = result["repository"]["pullRequests"]["nodes"]
    return pr_nodes[0] if pr_nodes else None


def _create_pr(
    forge_info: info.GitHubInfo,
    change_id: jj.ChangeId,
    head_ref: str,
    base_ref: str,
    draft: bool,
) -> UploadPr:
    descr = jj.change_info(change_id, "self.description()")
    title, body = descr.split("\n", 1) if "\n" in descr else (descr, "")

    result = forge_info.client.graphql(
        f"""
            mutation CreatePullRequest($input: CreatePullRequestInput!) {{
                createPullRequest(input: $input) {{
                    pullRequest {{
                        {PR_FIELDS}
                    }}
                }}
            }}
        """,
        {
            "input": {
                "repositoryId": forge_info.repo_id,
                "headRefName": head_ref,
                "baseRefName": base_ref,
                "title": title,
                "body": body,
                "draft": draft,
            }
        },
    )
    pr = result["createPullRequest"]["pullRequest"]
    log.info(f"PR #{pr['number']} = {head_ref} -> {base_ref}")
    print(f"Created pull request #{pr['number']} ({title})")
    return pr


def _update_pr(
    forge_info: info.GitHubInfo,
    change_id: jj.ChangeId,
    pr: UploadPr,
    base_ref: str,
    message: str | None,
) -> UploadPr:
    descr = jj.change_info(change_id, "self.description()")
    title, body = descr.split("\n", 1) if "\n" in descr else (descr, "")

    changes = {}
    if base_ref != pr["baseRefName"]:
        changes["baseRefName"] = base_ref
    if title != pr["title"]:
        changes["title"] = title
    if body != pr["body"]:
        changes["body"] = body

    if changes:
        result = forge_info.client.graphql(
            f"""
                mutation UpdatePullRequest($input: UpdatePullRequestInput!) {{
                    updatePullRequest(input: $input) {{
                        pullRequest {{
                            {PR_FIELDS}
                        }}
                    }}
                }}
            """,
            {"input": {"pullRequestId": pr["id"], **changes}},
        )
        updated_pr = result["updatePullRequest"]["pullRequest"]

        # TODO: if the contents of the PR have changed, add the message as a comment
        # (we don't want to add a comment every time, because sometimes we only
        # update a single commit in a stack)
        # if message is not None:
        #    ...

        print(f"Updated PR #{updated_pr['number']} ({title})")
    else:
        print(f"No changes needed for PR #{pr['number']} ({title})")
    return pr
