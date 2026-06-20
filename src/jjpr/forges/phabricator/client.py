import json
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs

import httpx

from ... import exc

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class PhabricatorClient(httpx.Client):
    """Custom httpx.Client for Phabricator.

    - Loads api.token from ~/.arcrc for the given base_url.
    - Adds api.token to POST request data.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL):
        super().__init__(base_url=base_url.copy_with(path="/api/"))

        token = None
        arc_conf = Path.home() / ".arcrc"
        if arc_conf.exists():
            with open(arc_conf) as f:
                data = json.load(f)
            for url, config in data.get("hosts", {}).items():
                if httpx.URL(url).host == base_url.host:
                    token = config.get("token")
                    break
        if not token:
            raise exc.UserError(f"API token for {base_url.host} not found in ~/.arcrc")
        self.token = token

    def request(self, *args, **kwargs) -> httpx.Response:
        response = super().request(*args, **kwargs)
        kvs = []
        for k, v in parse_qs(response.request.content.decode()).items():
            kvs.append(f"{k}: {', '.join(v)}")
        kvss = "\n     ".join(kvs)
        log.debug(
            f"API call:\n"
            f"  {response.request.method} {response.request.url} = {response.status_code}\n"
            f"  <- {kvss}\n"
            f"  -> {response.text}"
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            e.add_note(e.response.text)
            raise
        js = response.json()
        if js.get("error_code"):
            raise Exception(
                f"Phabricator API error: {js['error_code']} - {js.get('error_info')}"
            )
        return response

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
        url: str | httpx.URL,
        *args,
        data: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> httpx.Response:
        formed_params = {
            "api.token": self.token,
        }
        self._struct2http(None, formed_params, data or {})
        return super().post(url, data=formed_params, *args, **kwargs)
