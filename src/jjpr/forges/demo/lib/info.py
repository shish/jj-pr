import typing as t

import httpx

from ...base import ForgeInfo


@t.final
class DemoInfo(ForgeInfo[None]):
    def __init__(self, remote: str):
        super().__init__(remote)
        self.forge_url = httpx.URL("https://demo.example.com")
        self.project_id = "demo/repo"


def get_forge_info(remote: str) -> DemoInfo:
    return DemoInfo(remote)
