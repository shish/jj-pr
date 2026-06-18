import json
import logging
import re
from pathlib import Path
from typing import Any, List, Optional

import httpx
from rich.pretty import pretty_repr

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class PhabricatorClient(httpx.Client):
    """HTTP client that automatically adds api.token to POST request data."""

    def __init__(self, token: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = token

    @staticmethod
    def _struct2http(base: Optional[str], formed_params: dict, params: dict) -> None:
        for key, value in params.items():
            if base:
                new_key = f"{base}[{key}]"
            else:
                new_key = key
            if isinstance(value, dict):
                PhabricatorClient._struct2http(new_key, formed_params, value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    PhabricatorClient._struct2http(
                        new_key, formed_params, {str(i): item}
                    )
            else:
                formed_params[new_key] = value

    def post(
        self,
        url: httpx.URL,
        *args,
        data: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> httpx.Response:
        formed_params = {
            "api.token": self.token,
        }
        self._struct2http(None, formed_params, data or {})
        return super().post(url, data=formed_params, *args, **kwargs)


class Phabricator(Forge):
    def __init__(self, remote: str, remote_url: httpx.URL):
        super().__init__(remote, remote_url)
        self.client = PhabricatorClient(
            token=_get_token(str(self.forge_url.host)),
            base_url=self.forge_url,
        )

    @property
    def project_id(self) -> str:
        arcconfig_path = Path(".arcconfig")
        if arcconfig_path.exists():
            with open(arcconfig_path) as f:
                arcconfig = json.load(f)
            if callsign := arcconfig.get("repository.callsign"):
                return callsign
        raise utils.UserError(
            "Could not determine project ID. Ensure .arcconfig exists and has 'repository.callsign' set."
        )

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = self.forge_url.join(f"/api/{endpoint}")
        log.debug(f"Making request to {url}:\n{pretty_repr(params)}")
        response = self.client.post(url, data=params)
        response.raise_for_status()
        result = response.json()
        log.debug(f"Response from {url}:\n{pretty_repr(result)}")
        if result.get("error_code"):
            raise utils.UserError(
                f"Phabricator API error: {result['error_code']} - {result.get('error_info')}"
            )
        return result["result"]

    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        changes = jj.specified_or_stack(ref, require_description=False)
        for change_id in changes:
            self._push_one(change_id, draft=draft, message=message)
            self._set_parents(change_id)

    def _push_one(
        self,
        change_id: str,
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        with jj.with_new(change_id):
            log.info(f"Pushing {change_id}")
            args = ["arc", "diff", "HEAD^"]
            if draft:
                args.append("--draft")
            if message:
                args.extend(["--message", message])
            utils.run(args, cap=False)

    def _change_to_revision(self, change_id: jj.ChangeID) -> Optional[PhRev]:
        d = jj.description_of(change_id)
        if m := re.search(r"Differential Revision:.*D(\d+)", d):
            return int(m.group(1))
        return None

    def _revision_to_phid(self, revision: PhRev) -> PhID:
        result = self._request(
            "differential.revision.search",
            params={"constraints": {"ids": [revision]}},
        )
        if not result["data"]:
            raise utils.UserError(f"Revision D{revision} not found")
        return result["data"][0]["phid"]

    def _set_parents(self, change_id: jj.ChangeID) -> None:
        parents = jj.change_ids(f"{change_id}- & mutable()")
        parent_revs = [self._change_to_revision(p) for p in parents]
        parent_revs = [p for p in parent_revs if p is not None]
        parent_phids = [self._revision_to_phid(p) for p in parent_revs]
        pstr = ", ".join(f"D{p}" for p in parent_revs)
        log.info(f"Setting parent revisions for {change_id}: {pstr}")
        self._request(
            "differential.revision.edit",
            params={
                "objectIdentifier": self._change_to_revision(change_id),
                "transactions": [
                    {"type": "parents.set", "value": parent_phids},
                ],
            },
        )

    def checkout(self, identifier: str) -> None:
        log.info(f"Checking out Phabricator diff {identifier}")
        utils.run(["arc", "patch", identifier], cap=False)

    def list(self, all_projects: bool = False) -> List[CRListItem]:
        log.info(
            f"Listing diffs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )

        myPHID = self._request("user.whoami")["phid"]
        rev_constraints = {
            "constraints": {
                "authorPHIDs": [myPHID],
                "statuses": [
                    "draft",
                    "needs-review",
                    "needs-revision",
                    "accepted",
                    "changes-planned",
                ],
            }
        }
        if not all_projects:
            rev_constraints["constraints"]["repositoryPHIDs"] = [
                self._request(
                    "diffusion.repository.search",
                    params={"constraints": {"callsigns": [self.project_id]}},
                )["data"][0]["phid"]
            ]
        revs = self._request(
            "differential.revision.search",
            params=rev_constraints,
        )["data"]

        return [
            CRListItem(
                forge_name="Phabricator",
                forge_url=self.forge_url,
                project_id=self.project_id,
                identifier=str(rev["id"]),
                title=rev["fields"]["title"],
                url=httpx.URL(rev["fields"]["uri"]),
                state=_colour_state(rev["fields"]["status"]["name"]),
                blockers="",
            )
            for rev in revs
        ]


def _get_token(hostname: str) -> str:
    token = None
    arc_conf = Path.home() / ".arcrc"
    if arc_conf.exists():
        with open(arc_conf) as f:
            data = json.load(f)
        for host, config in data.get("hosts", {}).items():
            if host.startswith(hostname):
                token = config.get("token")
                break
    if not token:
        raise utils.UserError(f"API token for {hostname} not found in ~/.arcrc")
    return token


def _colour_state(state: str) -> str:
    s2c = {
        "Draft": "cyan",
        "Changes Planned": "cyan",
        "Rejected": "red",
        "Needs Review": "yellow",
        "Accepted": "green",
    }
    c = s2c.get(state, "yellow")
    return f"[{c}]{state}[/{c}]"
