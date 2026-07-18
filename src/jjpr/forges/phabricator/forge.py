import json
import logging
import re
import socket
import typing as t
from pathlib import Path

import httpx

from ... import exc
from ...utils import exec, git, jj
from .. import cr
from ..base import Forge
from . import arcdiff
from .client import PhabricatorClient

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class Phabricator(Forge):
    def __init__(self, remote: str):
        super().__init__(remote)

        config_path = Path(".arcconfig")
        if config_path.exists():
            repo_config = json.loads(Path(".arcconfig").read_text())
        else:
            repo_config = {}

        if uri := repo_config.get("phabricator.uri"):
            self.forge_url = httpx.URL(uri)
        else:
            self.forge_url = self.remote_url.copy_with(path=None)
        self.client = PhabricatorClient(self.forge_url)

        if callsign := repo_config.get("repository.callsign"):
            self.project_id = callsign
        else:
            self.project_id = self.client.call(
                "diffusion.repository.search",
                constraints={"uris": [str(self.remote_url)]},
            )["data"][0]["fields"]["callsign"]

        if merge_target := repo_config.get("arc.land.onto.default"):
            self.merge_target = merge_target
        else:
            self.merge_target = git.get_merge_target()

        log.info(
            f"Phabricator settings:\n  forge_url: {self.forge_url}\n  project_id: {self.project_id}\n  merge_target: {self.merge_target}"
        )

    def upload_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        changes = jj.change_id(ref) if ref else jj.pushable_stack()
        log.info(f"Pushing {ref} ({changes})")
        for change_id in changes:
            self._push_one(change_id, draft=draft, message=message)

    def _push_one(
        self,
        change_id: str,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        log.info(f"Pushing {change_id}")

        # Revision data to send to differential.revision.edit
        data: dict[str, t.Any] = {
            "transactions": [],
        }

        rev = self._change_to_revision(change_id)
        if rev:
            log.info(f"Updating revision D{rev} for {change_id}")
            data["objectIdentifier"] = self._revision_to_phid(rev)
        else:
            log.info(f"Creating new revision for {change_id}")
            trs = self._parse_commit_message(change_id)
            data["transactions"].extend(trs)

        # Create a diff
        diff_data = self._push_change_to_differential(change_id)
        data["transactions"].append({"type": "update", "value": diff_data["phid"]})

        # Push to staging (if configured)
        self._push_change_to_staging(change_id, diff_data)

        # Set parent diff if our parent commit contains a diff ID
        if parent_phids := self._get_parent_phids(change_id):
            data["transactions"].append({"type": "parents.set", "value": parent_phids})

        # If --draft, set that flag
        if draft:
            data["transactions"].append({"type": "draft", "value": "true"})

        # Create-or-update the revision
        revision_data = self.client.call("differential.revision.edit", **data)
        revision_id = revision_data["object"]["id"]
        revision_url = self.forge_url.copy_with(path=f"/D{revision_id}")

        # TODO: add a message if -m is passed

        # Make sure the commit message contains the Differential Revision line
        if not rev:
            orig_msg = jj.description_of(change_id)
            new_msg = orig_msg + f"\n\nDifferential Revision: {revision_url}"
            jj.describe(r=change_id, m=new_msg)
            print(f"Created revision {revision_url} for {change_id}")
        else:
            print(f"Updated revision {revision_url} for {change_id}")

    def _parse_commit_message(self, change_id: jj.ChangeID) -> list[dict[str, t.Any]]:
        trs = self.client.call(
            "differential.parsecommitmessage",
            corpus=jj.description_of(change_id),
        )["transactions"]
        for r in {"title", "summary", "testPlan"}:
            for tr in trs:
                if tr["type"] == r:
                    break
            else:
                trs.append({"type": r, "value": "-"})
        return trs

    def _get_parent_phids(self, change_id: jj.ChangeID) -> list[PhID]:
        parent_chids = jj.change_ids(f"{change_id}- & mutable()")
        parent_revs = [self._change_to_revision(p) for p in parent_chids]
        parent_phids = [self._revision_to_phid(p) for p in parent_revs if p is not None]
        return parent_phids

    def _push_change_to_differential(self, change_id: jj.ChangeID) -> dict[str, t.Any]:
        diff_text = jj.run("diff", "--git", "-r", change_id)
        changes = arcdiff.changes_to_conduit(arcdiff.parse_diff(diff_text))
        diff_data = self.client.call(
            "differential.creatediff",
            changes=changes,
            sourceMachine=socket.gethostname(),
            sourcePath=jj.root(),
            branch=self.merge_target,
            sourceControlSystem="git",
            sourceControlPath="/",
            sourceControlBaseRevision=jj.commit_id(f"{change_id}-"),
            creationMethod="jjpr",
            lintStatus=arcdiff.LintStatus.NONE,
            unitStatus=arcdiff.UnitStatus.NONE,
            repositoryPHID=self._callsign_to_phid(self.project_id),
        )
        return diff_data

    def _push_change_to_staging(
        self, change_id: jj.ChangeID, diff_data: dict[str, t.Any]
    ) -> None:
        if staging_uri := self._get_staging_url():
            log.info(f"Pushing {change_id} to staging at {staging_uri}")
            base_hash = jj.commit_id(f"{change_id}-")
            diff_hash = jj.commit_id(change_id)
            exec.run(
                "git",
                "push",
                "--no-verify",
                "--",
                staging_uri,
                f"{base_hash}:refs/tags/phabricator/base/{diff_data['diffid']}",
                f"{diff_hash}:refs/tags/phabricator/diff/{diff_data['diffid']}",
                cap=False,
            )

    def _get_staging_url(self) -> str | None:
        # repository.query is deprecated, but diffusion.repository.search
        # doesn't return the staging URI, so...
        # (ignore type because returning an array is correct but non-standard)
        repo_data = self.client.call(  # type: ignore
            "repository.query",
            callsigns=[self.project_id],
        )[0]
        return repo_data.get("staging", {}).get("uri")

    def _change_to_revision(self, change_id: jj.ChangeID) -> PhRev | None:
        d = jj.description_of(change_id)
        if m := re.search(r"Differential Revision:.*D(\d+)", d):
            return int(m.group(1))
        return None

    def _revision_to_phid(self, revision: PhRev) -> PhID:
        result = self.client.call(
            "differential.revision.search",
            constraints={"ids": [revision]},
        )
        if not result["data"]:
            raise exc.UserError(f"Revision D{revision} not found")
        return result["data"][0]["phid"]

    def _callsign_to_phid(self, callsign: str) -> PhID:
        return self.client.call(
            "diffusion.repository.search",
            constraints={"callsigns": [callsign]},
        )["data"][0]["phid"]

    def download_cr(self, identifier: str) -> None:
        log.info(f"Checking out Phabricator diff {identifier}")
        exec.run("arc", "patch", identifier, cap=False)

    def _my_open_crs(self) -> list[dict[str, t.Any]]:
        myPHID = self.client.call("user.whoami")["phid"]
        revs = self.client.call(
            "differential.revision.search",
            constraints={
                "authorPHIDs": [myPHID],
                "repositoryPHIDs": [self._callsign_to_phid(self.project_id)],
                "statuses": [
                    "draft",
                    "needs-review",
                    "needs-revision",
                    "accepted",
                    "changes-planned",
                ],
            },
        )["data"]
        return revs

    def list_crs(self) -> list[cr.CodeReview]:
        log.info(f"Listing diffs for {self.remote_url} ({self.project_id})")
        revs = self._my_open_crs()
        return [
            cr.CodeReview(
                forge=self,
                cr_id=str(rev["id"]),
                title=cr.Title(
                    text=rev["fields"]["title"],
                    url=httpx.URL(rev["fields"]["uri"]),
                ),
                state=_colour_state(
                    state=rev["fields"]["status"]["name"],
                    url=httpx.URL(rev["fields"]["uri"]),
                ),
                blockers=[],
            )
            for rev in revs
        ]

    def log(self, args: list[str]) -> str:
        def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, cr.State]:
            return {
                f"D{rev['id']}": _colour_state(
                    state=rev["fields"]["status"]["name"],
                    url=httpx.URL(rev["fields"]["uri"]),
                )
                for rev in self.client.call(
                    "differential.revision.search",
                    constraints={"ids": [int(x[1:]) for x in pr_ids]},
                )["data"]
            }

        return jj.log_with_annotations(
            args,
            """
            commit.description()
                .lines()
                .filter(|line| line.starts_with("Differential Revision: "))
                .map(|line| line.match(regex:"D[0-9]+"))
                .join(",")
            """,
            _pr_ids_to_states,
        )


def _colour_state(state: str, url: httpx.URL) -> cr.State:
    c = {
        "Draft": "cyan",
        "Changes Planned": "cyan",
        "Rejected": "red",
        "Needs Review": "yellow",
        "Accepted": "green",
    }.get(state, "yellow")
    return cr.State(state, color=c, url=url)
