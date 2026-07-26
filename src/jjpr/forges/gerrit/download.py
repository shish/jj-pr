import logging

from ...utils import exec
from ._info import get_forge_info

log = logging.getLogger(__name__)


def download_cmd(remote: str, identifier: str) -> None:
    f = get_forge_info(remote)
    log.info(f"Fetching Gerrit change {identifier}")
    # Query API to get the latest patch set number
    change_data_response = f.client.get(
        f"changes/{identifier}?o=CURRENT_REVISION"
    ).json()

    # Ensure response is a dict
    if not isinstance(change_data_response, dict):
        log.error(f"Invalid response type for change {identifier}")
        return

    # Get the latest patch set revision
    current_rev = change_data_response.get("current_revision")
    if not current_rev:
        log.error(f"Could not determine current revision for change {identifier}")
        return

    # Fetch the latest patch set
    remote_id = f"refs/remotes/{f.remote}/change-{identifier}"
    exec.run("git", "fetch", f.remote, f"{current_rev}:{remote_id}")
    exec.run("git", "checkout", remote_id)
