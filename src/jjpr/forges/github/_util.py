import typing as t

import httpx

from ...utils import cr

# GraphQL selection for a PullRequest's status checks, based on the last commit.
STATUS_CHECK_FIELDS = """
  commits(last: 1) {
    nodes {
      commit {
        statusCheckRollup {
          contexts(first: 100) {
            nodes {
              __typename
              ... on StatusContext {
                context
                state
                targetUrl
              }
              ... on CheckRun {
                name
                status
                conclusion
                detailsUrl
              }
            }
          }
        }
      }
    }
  }
"""

# GraphQL selection for a PullRequest's reviews.
REVIEW_FIELDS = """
  reviews(first: 100) {
    nodes {
      state
    }
  }
"""


def flatten_checks(pr: dict[str, t.Any]) -> list[dict[str, t.Any]]:
    """
    Turn the nested `commits.nodes[0].commit.statusCheckRollup.contexts.nodes`
    structure (queried via STATUS_CHECK_FIELDS) into a flat list of
    {name, conclusion, detailsUrl} dicts, merging the CheckRun and
    StatusContext variants into a single shape.
    """
    contexts: list[dict[str, t.Any]] = []
    commit_nodes = pr.get("commits", {}).get("nodes", [])
    if commit_nodes:
        rollup = commit_nodes[0]["commit"].get("statusCheckRollup")
        if rollup:
            contexts = rollup["contexts"]["nodes"]

    checks: list[dict[str, t.Any]] = []
    for context in contexts:
        if context["__typename"] == "CheckRun":
            checks.append(
                {
                    "name": context["name"],
                    "conclusion": context.get("conclusion"),
                    "detailsUrl": context.get("detailsUrl"),
                }
            )
        if context["__typename"] == "StatusContext":
            checks.append(
                {
                    "name": context["context"],
                    "conclusion": context.get("state"),
                    "detailsUrl": context.get("targetUrl"),
                }
            )
    return checks


def pr2state(
    pr: dict[str, t.Any],
) -> cr.State:
    is_draft = pr["isDraft"]
    reviews = pr["reviews"]["nodes"]
    url = httpx.URL(pr["url"])

    if reviews is None:
        reviews = []

    # Determine display state based on draft and review status
    if is_draft:
        display_state = "Draft"
        color = "cyan"
    else:
        # Check review status
        has_approved = any(r.get("state") == "APPROVED" for r in reviews)
        has_rejected = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)

        if has_rejected:
            display_state = "Rejected"
            color = "red"
        elif has_approved:
            display_state = "Accepted"
            color = "green"
        else:
            display_state = "Needs Review"
            color = "yellow"

    return cr.State(display_state, color=color, url=url)
