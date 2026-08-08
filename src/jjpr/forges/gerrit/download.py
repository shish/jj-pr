import logging

from ...utils import exec
from .lib import info

log = logging.getLogger(__name__)


def download_cmd(remote: str, identifier: str) -> None:
    forge_info = info.get_forge_info(remote)
    log.info(f"Fetching Gerrit change {identifier}")
    # Query API to get the latest patch set number
    change_data_response = forge_info.client.get(
        f"changes/{identifier}?o=CURRENT_REVISION"
    ).json()

    # Get the latest patch set revision
    current_rev = change_data_response.get("current_revision")
    if not current_rev:  # pragma: no cover - can't figure out how to repro this
        log.error(f"Could not determine current revision for change {identifier}")
        return

    # Fetch the latest patch set
    remote_id = f"refs/remotes/{forge_info.remote}/change-{identifier}"
    exec.run("git", "fetch", forge_info.remote, f"{current_rev}:{remote_id}")
    exec.run("git", "checkout", remote_id)
