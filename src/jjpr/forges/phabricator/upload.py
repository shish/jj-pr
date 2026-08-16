import json
import logging
import re
import socket
import typing as t
from pathlib import Path

from ...utils import exc, exec, jj
from . import arc
from .lib import client, info

log = logging.getLogger(__name__)


def upload_cmd(
    remote: str,
    ref: jj.RevSet | None,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = True,
) -> None:
    forge_info = info.get_forge_info(remote)
    changes = jj.change_ids(jj.revset(ref)) if ref else jj.pushable_stack()
    log.info(f"Pushing {ref} ({changes})")
    for change_id in changes:
        _push_one(
            forge_info, change_id, draft=draft, message=message, pre_commit=pre_commit
        )


def _push_one(
    forge_info: info.PhabricatorInfo,
    change_id: jj.ChangeId,
    draft: bool = False,
    message: str | None = None,
    pre_commit: bool = False,
) -> None:
    client = forge_info.client
    log.info(f"Pushing {change_id}")

    # Revision data to send to differential.revision.edit
    data: dict[str, t.Any] = {
        "transactions": [],
    }

    rev = _change_to_revision(change_id)
    if rev:
        log.info(f"Updating revision D{rev} for {change_id}")
        data["objectIdentifier"] = _revision_to_phid(client, rev)
    else:
        log.info(f"Creating new revision for {change_id}")
        trs = _parse_commit_message(client, change_id)
        data["transactions"].extend(trs)

    # Create a diff
    diff_phid = _push_change_to_differential_via_subprocess(
        client, forge_info, change_id, pre_commit
    )
    data["transactions"].append({"type": "update", "value": diff_phid})

    # Set parent diff if our parent commit contains a diff ID
    if parent_phids := _get_parent_phids(client, change_id):
        data["transactions"].append({"type": "parents.set", "value": parent_phids})

    # If --draft, set that flag
    if draft:
        data["transactions"].append({"type": "draft", "value": "true"})

    # Create-or-update the revision
    revision_data = client.call("differential.revision.edit", **data)
    revision_id = revision_data["object"]["id"]
    revision_url = forge_info.forge_url.copy_with(path=f"/D{revision_id}")

    # TODO: add a message if -m is passed

    # Make sure the commit message contains the Differential Revision line
    if not rev:
        orig_msg = jj.description_of(change_id)
        new_msg = orig_msg + f"\n\nDifferential Revision: {revision_url}"
        jj.describe(r=change_id, m=new_msg)
        print(f"Created revision {revision_url} for {change_id}")
    else:
        print(f"Updated revision {revision_url} for {change_id}")


def _parse_commit_message(
    client: client.PhabricatorClient, change_id: jj.ChangeId
) -> client.PhTransactions:
    trs = client.call(
        "differential.parsecommitmessage",
        corpus=jj.description_of(change_id),
    )["transactions"]
    for r in ["title", "summary", "testPlan"]:
        for tr in trs:
            if tr["type"] == r:
                break
        else:
            trs.append({"type": r, "value": "-"})
    return trs


def _get_parent_phids(
    client: client.PhabricatorClient, change_id: jj.ChangeId
) -> list[client.PhId]:
    parent_chids = jj.change_ids(jj.revset(f"{change_id}- & mutable()"))
    parent_revs = [_change_to_revision(p) for p in parent_chids]
    parent_phids = [_revision_to_phid(client, p) for p in parent_revs if p is not None]
    return parent_phids


def _push_change_to_differential_via_subprocess(
    client: client.PhabricatorClient,
    forge_info: info.PhabricatorInfo,
    change_id: jj.ChangeId,
    pre_commit: bool = True,
) -> client.PhId:
    if Path(".arclint").exists():
        with jj.with_edit(change_id):
            exec.run("arc", "lint", "--apply-patches")
    with jj.with_new(change_id):
        text = exec.run("arc", "diff", "HEAD^", "--only", "--json")
    # arc logs go to stdout...
    diff_num = json.loads(text.splitlines()[-1])["diffID"]
    diff_phid = client.call(
        "differential.diff.search",
        constraints={"ids": [diff_num]},
    )["data"][0]["phid"]
    return diff_phid


def _push_change_to_differential_natively(
    client: client.PhabricatorClient,
    forge_info: info.PhabricatorInfo,
    change_id: jj.ChangeId,
    pre_commit: bool = True,
) -> client.PhId:
    # Run pre-commit hooks if requested
    with jj.with_edit(change_id):
        lint_info = arc.lint.lint_current_diff(pre_commit)
        unit_info = arc.unit.unit_current_diff(pre_commit)

    diff_text = jj.run("diff", "--git", "-r", change_id)
    changes = arc.diff.changes_to_conduit(arc.diff.parse_diff(diff_text))
    diff_data = client.call(
        "differential.creatediff",
        changes=changes,
        sourceMachine=socket.gethostname(),
        sourcePath=jj.root(),
        branch=forge_info.default_merge_target,
        sourceControlSystem="git",
        sourceControlPath="/",
        sourceControlBaseRevision=jj.commit_id(
            jj.change_id(jj.revset(f"{change_id}-"))
        ),
        creationMethod="jjpr",
        lintStatus=lint_info[0],
        unitStatus=unit_info[0],
        repositoryPHID=_callsign_to_phid(client, forge_info.project_id),
    )
    client.call(
        "differential.setdiffproperty",
        diff_id=diff_data["diffid"],
        name="arc:lint",
        data=json.dumps(
            {
                "status": lint_info[0],
                "messages": lint_info[1],
            }
        ),
    )
    client.call(
        "differential.setdiffproperty",
        diff_id=diff_data["diffid"],
        name="arc:unit",
        data=json.dumps(
            {
                "status": unit_info[0],
                "messages": unit_info[1],
            }
        ),
    )

    if staging_uri := _get_staging_url(client, forge_info.project_id):
        log.info(f"Pushing {change_id} to staging at {staging_uri}")
        base_hash = jj.commit_id(jj.change_id(jj.revset(f"{change_id}-")))
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

    return diff_data["phid"]


def _get_staging_url(client: client.PhabricatorClient, callsign: str) -> str | None:
    # repository.query is deprecated, but diffusion.repository.search
    # doesn't return the staging URI, so...
    # (ignore type because returning an array is correct but non-standard)
    repo_data = client.call(  # type: ignore
        "repository.query",
        callsigns=[callsign],
    )[0]
    return repo_data.get("staging", {}).get("uri")


def _change_to_revision(change_id: jj.ChangeId) -> client.PhRevNum | None:
    d = jj.description_of(change_id)
    if m := re.search(r"Differential Revision:.*D(\d+)", d):
        return client.PhRevNum(int(m.group(1)))
    return None


def _revision_to_phid(
    client: client.PhabricatorClient, revision: client.PhRevNum
) -> client.PhId:
    result = client.call(
        "differential.revision.search",
        constraints={"ids": [revision]},
    )
    if not result["data"]:
        raise exc.UserError(f"Revision D{revision} not found")
    return result["data"][0]["phid"]


def _callsign_to_phid(client: client.PhabricatorClient, callsign: str) -> client.PhId:
    return client.call(
        "diffusion.repository.search",
        constraints={"callsigns": [callsign]},
    )["data"][0]["phid"]
