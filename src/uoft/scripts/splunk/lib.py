from functools import cached_property
from pathlib import Path

from uoft.core.api import APIBase
from uoft.core.types import SecretStr
from uoft.core import logging

logger = logging.getLogger(__name__)


class API(APIBase):
    def __init__(
        self,
        host: str,
        token: SecretStr,
        **kwargs
    ):
        super().__init__(host, api_root="/services", **kwargs)
        self.token = token

    def login(self):
        self.headers["Authorization"] = f"Bearer {self.token.get_secret_value()}"

    def start_search(self, query: str, earliest_time: str = "-15m", latest_time: str = "now"):
        logger.info(f"Starting search for query: {query}")
        res = self.post(
            url=self.api_url / "search/jobs",
            data={
                "search": f"search {query}",
                "earliest_time": earliest_time,
                "latest_time": latest_time,
            },
        )
        assert res.status_code == 201, f"Failed to start search: {res.text}"
        assert res.links.get('info', {}).get('url'), f"Failed to get search ID: {res.text}"
        return res.links.get('info', {})['url']

    def get_search_status(self, sid: str):
        logger.info(f"Getting search status for SID: {sid}")
        res = self.get(
            url=self.api_url / f"search/jobs/{sid}",
            params={"output_mode": "json"},
        )
        return res.json()["entry"][0]["content"]

    def get_search_results(self, sid: str, output_mode: str = "json"):
        logger.info(f"Getting search results for SID: {sid}")
        res = self.get(
            url=self.api_url / f"search/jobs/{sid}/results",
            params={"output_mode": output_mode},
        )
        if output_mode == "json":
            return res.json()["results"]
        else:
            return res.text
