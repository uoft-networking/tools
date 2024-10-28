from functools import cached_property
from pathlib import Path

from uoft_core.api import APIBase
from uoft_core.types import SecretStr
from uoft_core import logging

logger = logging.getLogger(__name__)


class API(APIBase):
    def __init__(
        self,
        base_url: str,
        username: str,
        password: SecretStr,
        api_key: SecretStr | None = None,
        device_group: str | None = None,
        create_missing_tags: bool = False,
        verify: bool | str = True,
    ):
        super().__init__(base_url, api_root="/restapi/v10.2", verify=verify)
        self.username = username
        self.password = password
        self.api_key = api_key
        self.device_group = device_group
        self.create_missing_tags = create_missing_tags

    def login(self):
        # PA NSM REST API supports basic authentication, so the login process is actually quite simple
        self.auth = (self.username, self.password.get_secret_value())
        if self.api_key:
            self.headers["X-PAN-KEY"] = self.api_key.get_secret_value()

    def generate_api_key(self):
        logger.info("Generating API key")
        res = self.post(
            url=self.url / "api",
            params=dict(type="keygen"),
            data=dict(user=self.username, password=self.password.get_secret_value()),
        )
        # response is XML, so we need to parse out the key
        key = res.text.partition("<key>")[2].partition("</key>")[0]
        self.api_key = SecretStr(key)
        return key

    def default_params(self):
        if self.device_group:
            return {"location": "device-group", "device-group": self.device_group}
        return {"location": "shared"}

    def default_payload(self):
        if self.device_group:
            return {"@location": "device-group", "@device-group": self.device_group}
        return {"@location": "shared"}
    
    def commit(self):
        assert self.api_key, "API key is required to commit changes"
        logger.info("Committing changes")
        res = self.post(self.url / 'api', params=dict(type='commit', cmd='<commit></commit>'))
        msg = res.text.partition("<msg>")[2].partition("</msg>")[0]
        logger.info(f"Commit result: {msg}")
        return msg

    @cached_property
    def tags(self) -> set[str]:
        logger.debug("Fetching tags")
        res = set()
        shared_tags = self.get("/Objects/Tags", params=dict(location="shared")).json()["result"]
        if shared_tags["@total-count"] != "0":
            res |= set(tag["@name"] for tag in shared_tags["entry"])
        if self.device_group:
            dg_tags = self.get("/Objects/Tags", params=self.default_params()).json()["result"]
            if dg_tags["@total-count"] != "0":
                res |= set(tag["@name"] for tag in dg_tags["entry"])
        return res

    def tag_create(self, name: str):
        logger.info(f"Creating tag '{name}'")
        params = self.default_params() | {"name": name}
        res = self.post(
            "/Objects/Tags",
            params=params,
            json={"entry": {"@name": name}},
        )
        self.tags.add(name)
        return res.json()

    def all_addresses(self) -> list[dict]:
        logger.info("Fetching networks")
        res = self.get("/Objects/Addresses", params=self.default_params()).json()["result"]
        if int(res["@total-count"]) > 0:
            return res["entry"]
        else:
            return []
        
    def network_list(self) -> list[dict]:
        return [n for n in self.all_addresses() if "ip-netmask" in n]

    def _tag_sort_fn(self, tag: str):
        # For our purposes here in UofT, not only do we want the tags to be consistently sorted, we also want to ensure
        # that the "net_type" tag is always first, if it exists
        if "net_type" in tag:
            return 0
        # for all other tags, we sort alpabetically by turning the first character into its ASCII value
        return ord(tag[0])

    def network_create(self, name: str, netmask: str, description: str | None = None, tags: set[str] | None = None):
        logger.info(f"Creating network '{name}' with netmask {netmask}")
        params = self.default_params() | {"name": name}
        payload: dict = self.default_payload() | {"@name": name, "ip-netmask": netmask}
        if description:
            payload["description"] = description
        if tags:
            for tag in tags.difference(self.tags):
                if self.create_missing_tags:
                    self.tag_create(tag)
                else:
                    raise ValueError(f"Tag '{tag}' does not exist")
            payload["tag"] = {"member": sorted(tags, key=self._tag_sort_fn)}
        return self.post(
            "/Objects/Addresses",
            params=params,
            json={"entry": [payload]},
        ).json()

    def network_rename(self, name: str, new_name: str):
        logger.info(f"Renaming network from {name} to {new_name}")
        self.post(
            "/Objects/Addresses:rename",
            params=self.default_params() | {"name": name, "newname": new_name},
        )

    def network_update(self, name: str, netmask: str, description: str | None = None, tags: set[str] | None = None):
        logger.info(f"Updating network '{name}' with netmask {netmask}")
        params = self.default_params() | {"name": name}
        payload: dict = self.default_payload() | {"@name": name, "ip-netmask": netmask}
        if description:
            payload["description"] = description
        if tags:
            for tag in tags.difference(self.tags):
                if self.create_missing_tags:
                    self.tag_create(tag)
                else:
                    raise ValueError(f"Tag '{tag}' does not exist")
            payload["tag"] = {"member": sorted(tags, key=self._tag_sort_fn)}
        return self.put(
            "/Objects/Addresses",
            params=params,
            json={"entry": [payload]},
        ).json()

    def network_delete(self, name: str):
        logger.info(f"Deleting network '{name}'")
        params = self.default_params() | {"name": name}
        payload: dict = self.default_payload() | {"@name": name}
        return self.delete(
            "/Objects/Addresses",
            params=params,
            json={"entry": [payload]},
        ).json()
