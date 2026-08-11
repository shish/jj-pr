import logging

from ...utils import cr
from .lib import info, util

log = logging.getLogger(__name__)


def list_cmd(remote: str) -> list[cr.CodeReview]:
    forge_info = info.get_forge_info(remote)
    log.info(f"Listing CRs on {forge_info.forge_url} ({forge_info.project_id})")

    query = f"owner:self+status:open+project:{forge_info.project_id}"
    changes_response = forge_info.client.get(
        f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
    ).json()

    return [
        util.parse_cr(change, forge_info.client, forge_info.forge_url)
        for change in changes_response
    ]
