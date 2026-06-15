import json
import logging
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class Gerrit(Forge):
    @property
    def gerrit_url(self) -> str:
        """Extract the Gerrit API base URL from remote_url.

        Converts URLs like:
        - https://gerrit.mycompany.com/a/project -> https://gerrit.mycompany.com
        - git@gerrit.mycompany.com:project -> https://gerrit.mycompany.com
        """
        parsed = urlparse(self.remote_url)

        # Handle SSH URLs (git@host:project)
        if parsed.scheme in ("", "ssh") or "@" in self.remote_url:
            # Extract host from git@host:project format
            host = self.remote_url.split("@")[1].split(":")[0]
            return f"https://{host}"

        # Handle HTTPS URLs
        if parsed.scheme in ("http", "https"):
            return f"{parsed.scheme}://{parsed.netloc}"

        raise ValueError(f"Cannot parse Gerrit URL from remote: {self.remote_url}")

    def push(self, ref: Optional[str]) -> None:
        if ref:
            change_id = jj.revset_to_changeid(ref)
            jj.run("gerrit", "upload", "-r", f"{change_id}::{change_id}")
        else:
            jj.run("gerrit", "upload", "-r", jj.closest_work())

    def checkout(self, identifier: str) -> None:
        log.info(f"Fetching Gerrit change {identifier}")
        # Query API to get the latest patch set number
        url = f"{self.gerrit_url}/a/changes/{identifier}?o=CURRENT_REVISION"
        with urlopen(url) as response:
            result = response.read().decode("utf-8")
        # Gerrit API returns a magic prefix that needs to be stripped
        if result.startswith(")]}'"):
            result = result[5:]
        change_data = json.loads(result)

        # Get the latest patch set revision
        current_rev = change_data.get("current_revision")
        if not current_rev:
            log.error(f"Could not determine current revision for change {identifier}")
            return

        # Fetch the latest patch set
        remote_id = f"refs/remotes/{self.remote}/change-{identifier}"
        utils.run(["git", "fetch", self.remote, f"{current_rev}:{remote_id}"])
        utils.run(["git", "checkout", remote_id])

    def list(self) -> None:
        """List the user's open changes in Gerrit, showing any blockers."""
        log.info(f"Listing open changes from {self.gerrit_url}")
        # Query Gerrit REST API for current user's open changes
        # 'owner:self' filters to current user, 'status:open' shows only open changes
        # DETAILED_LABELS shows reviewer votes and blocking votes
        url = f"{self.gerrit_url}/a/changes/?q=owner:self+status:open&o=DETAILED_LABELS&o=MESSAGES"
        with urlopen(url) as response:
            result = response.read().decode("utf-8")
        # Gerrit API returns a magic prefix that needs to be stripped
        if result.startswith(")]}'"):
            result = result[5:]
        changes = json.loads(result)

        if not changes:
            print("No open changes found.")
            return

        crs = []
        for change in changes:
            number = change.get("_number", "N/A")
            subject = change.get("subject", "N/A")
            status = change.get("status", "N/A")

            # Check for blockers
            blockers = []
            labels = change.get("labels", {})
            for label_name, label_data in labels.items():
                votes = label_data.get("all", [])
                for vote in votes:
                    value = vote.get("value")
                    # Check for blocking votes (-2) or negative votes (-1)
                    if value == -2:
                        blocker_name = vote.get("name", "Unknown")
                        blockers.append(f"Blocked by {blocker_name} ({label_name})")
                    elif value == -1:
                        blocker_name = vote.get("name", "Unknown")
                        blockers.append(f"{label_name}: {blocker_name}")

            blocker_str = f" [{', '.join(blockers)}]" if blockers else ""
            change_url = f"{self.gerrit_url}/c/{number}" if number != "N/A" else None
            crs.append(
                CRListItem(
                    identifier=str(number),
                    title=subject,
                    url=change_url,
                    extra={"status": status, "blockers": blocker_str},
                )
            )

        self.display_list(crs)
