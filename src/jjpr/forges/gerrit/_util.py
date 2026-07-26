import typing as t

import httpx

from ...utils import cr
from ._client import GerritClient


def get_checks(client: GerritClient, change_number: int) -> list[dict[str, t.Any]]:
    """Fetch CI check statuses for a change via the Gerrit checks plugin.

    Returns an empty list if the checks plugin isn't installed on this
    Gerrit instance.
    """
    try:
        response = client.get(
            f"changes/{change_number}/revisions/current/checks?o=CHECKER"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return []
        raise
    return response.json()


def colour_state(
    is_private: bool = False,
    work_in_progress: bool = False,
    blockers: bool = False,
    url: httpx.URL | None = None,
) -> cr.State:
    if is_private:
        state = "Private"
        color = "cyan"
    elif work_in_progress:
        state = "Draft"
        color = "cyan"
    elif blockers:
        state = "Blocked"
        color = "yellow"
    else:
        state = "Accepted"
        color = "green"

    return cr.State(state, color=color, url=url)
