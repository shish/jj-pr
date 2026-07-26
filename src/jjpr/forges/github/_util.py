import typing as t

import httpx

from ...utils import cr


def colour_state(
    is_draft: bool = False,
    reviews: list[t.Any] | None = None,
    url: httpx.URL | None = None,
) -> cr.State:
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
