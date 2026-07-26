import httpx

from ..base import ForgeInfo


def get_forge_info(remote: str) -> ForgeInfo[None]:
    f = ForgeInfo[None](remote)
    f.forge_url = httpx.URL("https://demo.example.com")
    f.project_id = "demo/repo"
    return f
