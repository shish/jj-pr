import typing as t

import httpx

from ....utils import cr
from . import client

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

REVIEW_THREAD_FIELDS = """
  reviewThreads(first: 100) {
    nodes {
      isResolved
    }
  }
"""


def flatten_checks(pr: client.PrJson) -> list[cr.Check]:
    """
    Turn the nested `commits.nodes[0].commit.statusCheckRollup.contexts.nodes`
    structure (queried via STATUS_CHECK_FIELDS) into a flat list of
    {name, conclusion, detailsUrl} dicts, merging the CheckRun and
    StatusContext variants into a single shape.
    """
    conclusion2state = {
        "SUCCESS": cr.CheckState.PASS,
        "PENDING": cr.CheckState.IN_PROGRESS,
        "FAILURE": cr.CheckState.FAIL,
    }

    contexts: list[dict[str, t.Any]] = []
    if commit_nodes := pr.get("commits", {}).get("nodes", []):
        rollup = commit_nodes[0]["commit"].get("statusCheckRollup")
        if rollup:
            contexts = rollup["contexts"]["nodes"]

    checks: list[cr.Check] = []
    for context in contexts:
        if context["__typename"] == "CheckRun":
            checks.append(
                cr.Check(
                    name=context["name"],
                    state=conclusion2state.get(
                        str(context.get("conclusion")), cr.CheckState.OTHER
                    ),
                    url=context.get("detailsUrl"),
                )
            )
        if context["__typename"] == "StatusContext":
            checks.append(
                cr.Check(
                    name=context["context"],
                    state=conclusion2state.get(
                        str(context.get("state")), cr.CheckState.OTHER
                    ),
                    url=context.get("targetUrl"),
                )
            )
    return checks


def pr2state(
    pr: client.PrJson,
) -> cr.ReviewState:
    is_draft = pr["isDraft"]
    reviews = pr["reviews"]["nodes"]

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

    return cr.ReviewState(display_state, color=color)


def count_unresolved(pr: client.PrJson) -> int:
    threads = pr.get("reviewThreads", {}).get("nodes", [])
    return sum(1 for thread in threads if not thread.get("isResolved", True))


def parse_cr(pr: client.PrJson) -> cr.CodeReview:
    return cr.CodeReview(
        cr_id="#" + str(pr["number"]),
        title=pr["title"],
        url=httpx.URL(pr["url"]),
        state=pr2state(pr),
        checks=flatten_checks(pr),
        unresolved_comments=count_unresolved(pr),
    )
