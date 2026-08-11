import logging
import typing as t

from ...utils import cr
from .lib import info, util

log = logging.getLogger(__name__)

_QUERY = f"""
  query PullRequestSearch($q: String!, $limit: Int!, $endCursor: String) {{
    search(query: $q, type: ISSUE, first: $limit, after: $endCursor) {{
      nodes {{
        ... on PullRequest {{
          number
          title
          state
          url
          isDraft
          {util.STATUS_CHECK_FIELDS}
          {util.REVIEW_FIELDS}
          {util.REVIEW_THREAD_FIELDS}
        }}
      }}
      pageInfo {{
        hasNextPage
        endCursor
      }}
    }}
  }}
"""


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge_info = info.get_forge_info(remote)
    log.info(f"Listing PRs on {forge_info.remote_url} ({forge_info.project_id})")

    prs: list[dict[str, t.Any]] = []
    end_cursor = None
    q = f"repo:{forge_info.project_id} author:@me state:open type:pr"
    while True:
        variables: dict[str, t.Any] = {
            "q": q,
            "limit": 100,
            "endCursor": end_cursor,
        }
        data = forge_info.client.graphql(_QUERY, variables)["search"]
        prs.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        end_cursor = data["pageInfo"]["endCursor"]

    return [util.parse_cr(pr) for pr in prs]
