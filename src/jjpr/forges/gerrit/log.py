from ...utils import cr, jj
from .lib import info, util


def log_cmd(remote: str, args: list[str]) -> str:
    forge_info = info.get_forge_info(remote)

    def _pr_ids_to_crs(pr_ids: list[str]) -> dict[str, cr.CodeReview]:
        # Fetch "my open reviews and their status" from gerrit,
        # index them by change ID. FIXME: "my open reviews" is
        # a poor approxmation of "the changes visible in jj log"
        query = f"owner:self+status:open+project:{forge_info.project_id}"
        changes_response = forge_info.client.get(
            f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
        ).json()
        return {
            str(change["change_id"]): util.parse_cr(
                change, forge_info.client, forge_info.forge_url
            )
            for change in changes_response
        }

    return jj.log_with_annotations(
        args,
        '"I" ++ commit.change_id().normal_hex() ++"6a6a6964"',
        _pr_ids_to_crs,
    )
