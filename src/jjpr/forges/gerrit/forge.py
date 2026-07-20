import logging
import re
import typing as t

import httpx

from ...utils import exec, git, jj, text
from .. import cr
from ..base import Forge
from .client import GerritClient

log = logging.getLogger(__name__)


class Gerrit(Forge):
    def __init__(self, remote: str):
        super().__init__(remote)
        if conf := jj.config_get("gerrit.review-url"):
            self.forge_url = httpx.URL(conf)
        else:
            if self.remote_url.scheme in {"http", "https"}:
                self.forge_url = self.remote_url.copy_with(path=None)
            else:
                self.forge_url = self.remote_url.copy_with(
                    scheme="https", username=None, port=None, path=None
                )
        if match := re.match(r"^/(a/)?(.*?)(\.git)?$", self.remote_url.path):
            self.project_id = match.group(2)
        self.merge_target = (
            jj.config_get("gerrit.default-remote-branch") or git.get_merge_target()
        )

        self.client = GerritClient(self.forge_url)

    def upload_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
        pre_commit: bool = True,
    ) -> None:
        if ref:
            change_id = jj.change_id(ref)
            range = f"{change_id}::{change_id}"
        else:
            range = jj.closest_work()
        log.info(f"Pushing {range} to gerrit")
        jj.gerrit_upload(
            r=range,
            wip=draft,
            message=message,
            remote_branch=self.merge_target,
        )

    def download_cr(self, identifier: str) -> None:
        log.info(f"Fetching Gerrit change {identifier}")
        # Query API to get the latest patch set number
        change_data_response = self.client.get(
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
        remote_id = f"refs/remotes/{self.remote}/change-{identifier}"
        exec.run("git", "fetch", self.remote, f"{current_rev}:{remote_id}")
        exec.run("git", "checkout", remote_id)

    def _get_checks(self, change_number: int) -> list[dict[str, t.Any]]:
        """Fetch CI check statuses for a change via the Gerrit checks plugin.

        Returns an empty list if the checks plugin isn't installed on this
        Gerrit instance.
        """
        try:
            response = self.client.get(
                f"changes/{change_number}/revisions/current/checks?o=CHECKER"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
        return response.json()

    def list_crs(self) -> list[cr.CodeReview]:
        """List the user's open changes in Gerrit, showing any blockers."""
        log.info(f"Listing open changes from {self.forge_url} ({self.project_id})")
        query = f"owner:self+status:open+project:{self.project_id}"
        changes_response = self.client.get(
            f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
        ).json()

        crs: list[cr.CodeReview] = []
        for change in changes_response:
            checks = []
            for check in self._get_checks(change["_number"]):
                if check.get("state") not in {"SUCCESSFUL", "NOT_RELEVANT"}:
                    checks.append(
                        cr.Blocker(
                            name=check.get("checker_name", check["checker_uuid"]),
                            color=_check_color(check.get("state")),
                            url=httpx.URL(check["url"]) if check.get("url") else None,
                        )
                    )

            blockers = []
            for req in change.get("submit_requirements", []):
                if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}:
                    req_name = re.sub("[^A-Z]+", "", req["name"])
                    blockers.append(cr.Blocker(req_name))

            crs.append(
                cr.CodeReview(
                    forge=self,
                    cr_id="c" + str(change["_number"]),
                    title=cr.Title(
                        change["subject"],
                        url=self.forge_url.join(f"/c/{change['_number']}"),
                    ),
                    state=_colour_state(
                        is_private=change.get("is_private", False),
                        work_in_progress=change.get("work_in_progress", False),
                        blockers=len(blockers) > 0,
                        url=self.forge_url.join(f"/c/{change['_number']}"),
                    ),
                    checks=checks,
                    blockers=blockers,
                )
            )

        return crs

    def log(self, args: list[str]) -> str:
        def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
            id_to_state: dict[str, str] = {}
            # Fetch "my open reviews and their status" from gerrit,
            # index them by change ID
            query = f"owner:self+status:open+project:{self.project_id}"
            changes_response = self.client.get(
                f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
            ).json()
            for change in changes_response:
                blockers = []
                for req in change.get("submit_requirements", []):
                    if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}:
                        req_name = re.sub("[^A-Z]+", "", req["name"])
                        blockers.append(req_name)
                state = _colour_state(
                    is_private=change.get("is_private", False),
                    work_in_progress=change.get("work_in_progress", False),
                    blockers=len(blockers) > 0,
                    url=self.forge_url.join(f"/c/{change['_number']}"),
                )
                checks = self._get_checks(change["_number"])
                id_to_state[str(change["change_id"])] = text.rich_str(
                    state, *[_check_to_str(check) for check in checks]
                )
            return id_to_state

        return jj.log_with_annotations(
            args,
            '"I" ++ commit.change_id().normal_hex() ++"6a6a6964"',
            _pr_ids_to_states,
        )


def _colour_state(
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


def _check_color(state: str | None) -> str:
    return {
        "SUCCESSFUL": "green",
        "NOT_RELEVANT": "green",
        "FAILED": "red",
    }.get(state or "", "yellow")


def _check_to_str(check: dict[str, t.Any]) -> str:
    state = check.get("state")
    if state in {"SUCCESSFUL", "NOT_RELEVANT"}:
        txt = "[green]✔[/green]"
    elif state == "FAILED":
        txt = "[red]✗[/red]"
    else:
        txt = "[yellow]…[/yellow]"
    if url := check.get("url"):
        return f"[link={url}]{txt}[/link]"
    return txt
