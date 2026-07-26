import logging

from ...utils import exec

log = logging.getLogger(__name__)


def download_cmd(remote: str, identifier: str) -> None:
    log.info(f"Checking out Phabricator diff {identifier}")
    exec.run("arc", "patch", identifier, cap=False)
