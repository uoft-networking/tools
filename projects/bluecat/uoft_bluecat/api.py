from typing import Any, Literal, overload
from functools import cached_property

from uoft_core.api import APIBase
from uoft_core import logging
from uoft_core.types import IPAddress, IPNetwork

logger = logging.getLogger(__name__)

IPAddressState = Literal[
    "UNASSIGNED",
    "DHCP_ABANDONED",
    "DHCP_ALLOCATED",
    "DHCP_EXCLUDED",
    "DHCP_FREE",
    "DHCP_LEASED",
    "DHCP_RESERVED",
    "DHCP_UNASSIGNED",
    "GATEWAY",
    "RESERVED",
    "RESTRICTED",
    "STATIC",
]


class API(APIBase):
    def __init__(self, base_url: str, username: str, password: str, verify: bool | str = True):
        super().__init__(base_url, api_root="api/v2", verify=verify)
        self.username = username
        self.password = password
        self.headers.update(
            {
                "Accept": "application/hal+json",
            }
        )
        # TODO: add support for custom / non-default configuration IDs

    def login(self):
        # /sessions is perhaps the only endpoint that doesn't require a change control comment to POST to,
        # so we call `super().post` instead of `self.post`
        token_response = (
            super().post(self.api_url / "sessions", json={"username": self.username, "password": self.password}).json()
        )
        # tok_data contains an apiToken field
        # you would think that the api token would be a valid Bearer token, but it's not
        # using it as such produces a 401 error
        # thanks bluecat!
        # token = tok_data['apiToken']
        # tok_data also contains a basicAuthenticationCredentials field
        # which is a base64 encoded string of the form "username:token"
        # and THAT is what we need to use to authenticate
        credentials = token_response["basicAuthenticationCredentials"]
        self.headers.update(
            {
                "Authorization": f"Basic {credentials}",
            }
        )
        super().login()

    def logout(self):
        # Bluecat REST V2 API does not have a logout endpoint
        pass

    def put(self, url: str, comment: str, data: Any = None, json: dict | list | None = None, **kwargs):
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        return super().put(url, data, json=json, **kwargs)

    def post(self, url: str, comment: str, data: Any = None, json: dict | list | None = None, **kwargs):
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        return super().post(url, data, json=json, **kwargs)

    def get_all(self, url, **kwargs) -> list[dict[str, Any]]:
        logger.info(f"Fetching all records in {url}")
        params = kwargs.pop("params", {})

        # set a high limit to lower the number of requests,
        # but only if a limit hasn't already been set
        params.setdefault("limit", 99999)
        res = self.get(url, params=params, **kwargs).json()
        data = res["data"]
        while res.get("_links", {}).get("next"):
            logger.debug(f"Fetching next page of addresses: {res['_links']['next']['href']}")
            res = self.get(res["_links"]["next"]["href"]).json()
            data.extend(res["data"])
        return data

    @cached_property
    def configuration_id(self) -> int:
        return self.get(self.api_url / "configurations").json()["data"][0]["id"]

    def find_parent_container(
        self, container_type: Literal["blocks", "networks", "any"], addr: str | IPAddress
    ) -> dict[str, Any]:
        """
        Find the smallest container that contains the given address

        Args:
            container_type (Literal['blocks', 'networks', 'any']): The type of container to search for.
                Can be 'blocks', 'networks', or 'any'.
            addr (str): The address to search for.

        Returns:
            dict[str, Any]: A dictionary representing the smallest container that contains the given address.

        Raises:
            ValueError: If no container of the specified type is found containing the address.
        """
        if container_type == "any":
            try:
                return self.find_parent_container("networks", addr)
            except ValueError:
                return self.find_parent_container("blocks", addr)
        assert container_type in ["blocks", "networks"]
        containers = self.get(self.api_url / container_type, params=dict(filter=f"range:contains('{addr}')")).json()[
            "data"
        ]
        if not containers:
            raise ValueError(f"No {container_type} found containing {addr}")
        # blocks returned from api are sorted from largest prefix (ie /8) to smallest (ie /24)
        # so the last block in the list is the smallest block that contains the address
        # for networks there can be only one so it doesn't matter if we index [0] or [-1]
        return containers[-1]

    def find_parent_block(self, addr: str | IPAddress) -> dict[str, Any]:
        """
        Finds the parent block of a given address.

        Args:
            addr (str): The address for which to find the parent block.

        Returns:
            dict[str, Any]: A dictionary representing the parent block.

        Raises:
            ValueError: If the address is invalid or not found.
        """
        return self.find_parent_container("blocks", addr)

    def find_parent_network(self, addr: str | IPAddress) -> dict[str, Any]:
        """
        Find the smallest network that contains the given address.

        Args:
            addr (str): The address to search for.

        Returns:
            dict[str, Any]: The smallest network that contains the given address.

        Raises:
            ValueError: If no network is found containing the given address.
        """
        return self.find_parent_container("networks", addr)

    @overload
    def create_address(
        self,
        parent_id: str | int,
        address: str,
        type_: Literal["IPv4Address", "IPv6Address"],
        name: str | None = None,
        comment: str = "Address created by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
        create_reverse_record: bool = True,
        **kwargs,
    ): ...

    @overload
    def create_address(
        self,
        parent_id: str | int,
        address: IPAddress,
        type_: None = None,
        name: str | None = None,
        comment: str = "Address created by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
        create_reverse_record: bool = True,
        **kwargs,
    ): ...

    def create_address(
        self,
        parent_id: str | int,
        address: str | IPAddress,
        type_: Literal["IPv4Address", "IPv6Address"] | None = None,
        name: str | None = None,
        comment: str = "Address created by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
        create_reverse_record: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        json = kwargs.setdefault("json", {})
        if isinstance(address, IPAddress):
            # If we're given an IPAddress object, we can derive type_ from it
            type_ = "IPv6Address" if address.version == 6 else "IPv4Address"
            address = str(address)
        else:
            assert type_ in ["IPv4Address", "IPv6Address"]
        json["type"] = type_
        json["address"] = address
        json["state"] = state
        if name:
            json["name"] = name

        if not create_reverse_record:
            kwargs.setdefault("headers", {})["x-bcn-create-reverse-record"] = "false"

        url = f"/networks/{parent_id}/addresses"
        if state == "GATEWAY" and type_ == "IPv4Address":
            # bluecat automatically creates a blank gateway address for each IPv4 network
            # and does not allow you to manually create your own.
            # we can achieve the desired effect by fetching and updating the existing gateway address
            # this is a workaround for the bluecat API's limitations
            gw_id = self.get(url, params=dict(limit=1, filter="state:'GATEWAY'")).json()["data"][0]["id"]
            return self.put(f"/addresses/{gw_id}", comment="Testing", **kwargs).json()
        return self.post(url, comment=comment, **kwargs).json()

    def create_network(
        self,
        parent_id: str | int,
        range: str | IPNetwork,
        type_: Literal["IPv4Network", "IPv6Network"] | None = None,
        prefix_length: int | None = None,
        name: str | None = None,
        comment: str = "Network created by uoft_bluecat tool",
        **kwargs,
    ):
        json = kwargs.setdefault("json", {})
        if isinstance(range, IPNetwork):
            # If we're given an IPAddress object, we can derive type_ from it
            type_ = "IPv6Network" if range.version == 6 else "IPv4Network"
            range = str(range)
        else:
            if prefix_length is not None:
                range = f"{range}/{prefix_length}"
            assert type_ in ["IPv4Network", "IPv6Network"]
        json["type"] = type_
        json["range"] = range
        if name:
            json["name"] = name
        assert parent_id != self.configuration_id, "Networks must be assigned to blocks, not configurations"
        url = f"/blocks/{parent_id}/networks"
        return self.post(url, comment=comment, **kwargs).json()

    def create_block(
        self,
        parent_id: str | int,
        range: str | IPNetwork,
        type_: Literal["IPv4Block", "IPv6Block"] | None = None,
        prefix_length: int | None = None,
        name: str | None = None,
        comment: str = "Block created by uoft_bluecat tool",
        **kwargs,
    ):
        json = kwargs.setdefault("json", {})
        if isinstance(range, IPNetwork):
            # If we're given an IPAddress object, we can derive type_ from it
            type_ = "IPv6Block" if range.version == 6 else "IPv4Block"
            range = str(range)
        else:
            if prefix_length is not None:
                range = f"{range}/{prefix_length}"
            assert type_ in ["IPv4Block", "IPv6Block"]
        json["type"] = type_
        json["range"] = range
        if name:
            json["name"] = name
        if parent_id == self.configuration_id:
            url = f"/configurations/{parent_id}/blocks"
        else:
            url = f"/blocks/{parent_id}/blocks"
        return self.post(url, comment=comment, **kwargs).json()
