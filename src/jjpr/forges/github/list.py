import logging
import typing as t

import httpx

from ...utils import cr
from . import _util
from ._client import GitHubClient
from ._info import get_forge_info

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
          {_util.STATUS_CHECK_FIELDS}
          {_util.REVIEW_FIELDS}
        }}
      }}
      pageInfo {{
        hasNextPage
        endCursor
      }}
    }}
  }}
"""


def _search_prs(client: GitHubClient, project_id: str) -> list[dict[str, t.Any]]:
    prs: list[dict[str, t.Any]] = []
    end_cursor = None
    q = f"repo:{project_id} author:@me state:open type:pr"
    while True:
        variables: dict[str, t.Any] = {
            "q": q,
            "limit": 100,
            "endCursor": end_cursor,
        }
        data = client.graphql(_QUERY, variables)["search"]
        prs.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        end_cursor = data["pageInfo"]["endCursor"]
    return prs


def list_cmd(remote: str) -> list[cr.CodeReview]:
    f = get_forge_info(remote)
    log.info(f"Listing PRs for {f.remote_url} ({f.project_id})")
    prs = _search_prs(f.client, f.project_id)

    crs: list[cr.CodeReview] = []
    c2c = {
        "SUCCESS": "green",
        "PENDING": "yellow",
        "FAILURE": "red",
    }
    for pr in prs:
        checks = [
            cr.Blocker(
                name=check["name"],
                color=c2c.get(check["conclusion"], "normal"),
                url=check["detailsUrl"],
            )
            for check in _util.flatten_checks(pr)
        ]

        crs.append(
            cr.CodeReview(
                cr_id="#" + str(pr["number"]),
                title=cr.Title(pr["title"], url=httpx.URL(pr["url"])),
                state=_util.pr2state(pr),
                checks=checks,
                blockers=[],
            )
        )
    return crs
