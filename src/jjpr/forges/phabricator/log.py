import logging

from ...utils import cr, jj
from .lib import info, util

log = logging.getLogger(__name__)


def log_cmd(remote: str, args: list[str]) -> str:
    forge_info = info.get_forge_info(remote)

    def _pr_ids_to_crs(pr_ids: list[str]) -> dict[str, cr.CodeReview]:
        revs = forge_info.client.call(
            "differential.revision.search",
            constraints={"ids": [int(x[1:]) for x in pr_ids]},
        )["data"]
        checks_by_diff = util.get_checks(
            forge_info.client,
            forge_info.forge_url,
            [rev["fields"]["diffPHID"] for rev in revs],
        )
        unresolved_by_rev = util.get_unresolved_counts(
            forge_info.client, [rev["id"] for rev in revs]
        )

        return {
            f"D{rev['id']}": util.parse_cr(rev, checks_by_diff, unresolved_by_rev)
            for rev in revs
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
        _pr_ids_to_crs,
    )
