import logging

from ...utils import exc, exec, git, jj
from .lib import client, info

log = logging.getLogger(__name__)


def upload_cmd(
    remote: str,
    ref: jj.RevSet | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    push_bookmark_template = jj.config_get("templates.git_push_bookmark")
    if not push_bookmark_template:
        raise exc.UserError(
            "Missing configuration: templates.git_push_bookmark. "
            "Please set it to a template for the bookmark name to "
            "use when pushing changes."
        )

    forge_info = info.get_forge_info(remote)
    changes = jj.change_ids(ref) if ref else jj.pushable_stack()

    # Create-or-update change-XYZ bookmarks for each change
    change_flags: list[str] = []
    for change_id in changes:
        change_flags.extend(["--change", change_id])
    jj.run("git", "push", *change_flags)

    prs: list[client.PrNum] = []
    for change_id in changes:
        my_branch = jj.change_info(change_id, push_bookmark_template)
        parent_id = jj.change_id(jj.revset(f"{change_id}-"))
        if jj.change_info(parent_id, "self.immutable()") == "true":
            base_branch = git.get_merge_target(remote)
        else:
            base_branch = jj.change_info(parent_id, push_bookmark_template)

        if existing_pr := _get_pr(forge_info, my_branch):
            prs.append(
                _update_pr(forge_info, change_id, existing_pr, base_branch, message)
            )
        else:
            prs.append(_create_pr(forge_info, change_id, my_branch, base_branch, draft))

    exec.run("gh", "stack", "link", *[str(pr) for pr in prs])


def _get_pr(forge_info: info.GitHubInfo, head_ref: str) -> client.PrJson | None:
    query = """
      query GetPullRequestByHeadRef($owner: String!, $name: String!, $headRef: String!, $states: [PullRequestState!]) {
        repository(owner: $owner, name: $name) {
          pullRequests(headRefName: $headRef, states: $states, first: 1) {
            nodes {
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
            }
          }
        }
      }
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
) -> client.PrNum:
    descr = jj.change_info(change_id, "self.description()")
    title, body = descr.split("\n", 1) if "\n" in descr else (descr, "")

    result = forge_info.client.graphql(
        """
          mutation CreatePullRequest($input: CreatePullRequestInput!) {
            createPullRequest(input: $input) {
              pullRequest {
                number
              }
            }
          }
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
    print(f"Created pull request #{pr['number']} for {head_ref} -> {base_ref}")
    return pr["number"]


def _update_pr(
    forge_info: info.GitHubInfo,
    change_id: jj.ChangeId,
    pr: client.PrJson,
    base_ref: str,
    message: str | None,
) -> client.PrNum:
    descr = jj.change_info(change_id, "self.description()")
    title, body = descr.split("\n", 1) if "\n" in descr else (descr, "")

    changes = {}
    if base_ref != pr["baseRefName"]:
        if pr["stack"] is not None:
            log.warning(
                f"Can't updte base ref for PR #{pr['number']} because it is part of a stack"
            )
        else:
            changes["baseRefName"] = base_ref
    if title != pr["title"]:
        changes["title"] = title
    if body != pr["body"]:
        changes["body"] = body

    if changes:
        result = forge_info.client.graphql(
            """
            mutation UpdatePullRequest($input: UpdatePullRequestInput!) {
                updatePullRequest(input: $input) {
                    pullRequest {
                        number
                    }
                }
            }
            """,
            {"input": {"pullRequestId": pr["id"], **changes}},
        )
        updated_pr = result["updatePullRequest"]["pullRequest"]

        # TODO: if the contents of the PR have changed, add the message as a comment
        # (we don't want to add a comment every time, because sometimes we only
        # update a single commit in a stack)
        # if message is not None:
        #    ...

        print(f"Updated PR #{updated_pr['number']}")
    else:
        print(f"No changes needed for PR #{pr['number']}")
    return pr["number"]
