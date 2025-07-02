from typing import Any, Literal, overload
from functools import cached_property

from uoft_core.api import APIBase, RESTAPIError
from uoft_core import logging
from uoft_core.types import IPAddress, IPNetwork

from . import type_stubs as ts

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
    def __init__(self, base_url: str, username: str, password: str, configuration: str | None = None, verify: bool | str = True):
        super().__init__(base_url, api_root="api/v2", verify=verify)
        self.username = username
        self.password = password
        self.headers.update({
            "Accept": "application/hal+json",
        })
        self.configuration = configuration

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
        self.headers.update({
            "Authorization": f"Basic {credentials}",
        })
        super().login()

        # Setting up configuration ID must be done before any API calls that require it
        # but cannot be done until after login, so we might as well do it here

        if self.configuration:
            # get the configuration ID by name
            configurations = self.get(self.url / "api/v2/configurations", params=dict(filter=f"name:eq('{self.configuration}')")).json()["data"]
            if not configurations:
                raise ValueError(f"Configuration '{self.configuration}' not found")
            if len(configurations) > 1:
                raise ValueError(f"Multiple configurations found with name '{self.configuration}'")
            conf_id = configurations[0]["id"]
            logger.info(f"Using configuration '{self.configuration}' with ID {conf_id}")
        else:
            # old behaviour, kept around for compatability
            conf_id = self.get(self.api_url / "configurations").json()["data"][0]["id"]
            logger.warning(f"No configuration specified, using first configuration found: {conf_id}")

        self.configuration_id = conf_id
        self.api_url = self.safe_append_path(self.url, f"api/v2/configurations/{conf_id}")


    def logout(self):
        # Bluecat REST V2 API does not have a logout endpoint
        pass

    def put(self, url: str, comment: str, data: Any = None, json: dict | list | None = None, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        return super().put(url, data, json=json, **kwargs)

    def post(self, url: str, comment: str, data: Any = None, json: dict | list | None = None, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
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
        params = dict(filter=f"range:contains('{addr}')")
        containers = self.get(self.api_url / container_type, params=params).json()["data"]
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

    def get_container_default_zones(
        self, container_id: str | int, container_type: Literal["blocks", "networks"]
    ) -> list[dict[str, Any]]:
        """
        Get the default zone for a given container.

        Args:
            container_id (str | int): The ID of the container.
            container_type (Literal['blocks', 'networks']): The type of the container.

        Returns:
            dict[str, Any]: A dictionary representing the default zone for the given container.
        """
        assert container_type in ["blocks", "networks"]
        return self.get(f"/{container_type}/{container_id}/defaultZones").json()["data"]

    # get an address by ip
    def get_address(self, address: str | IPAddress, **kwargs) -> dict[str, Any]:
        """
        Get an address by its IP.

        Args:
            address (str | IPAddress): The IP address to search for.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The address object if found, otherwise raises an error.
        """
        return self.get("/addresses", params=dict(filter=f"address:eq('{address}')"), **kwargs).json()

    @overload
    def create_address(
        self,
        address: str,
        type_: Literal["IPv4Address", "IPv6Address"],
        **kwargs,
    ): ...

    @overload
    def create_address(
        self,
        address: IPAddress,
        type_: None = None,
        **kwargs,
    ): ...

    def create_address(
        self,
        address: str | IPAddress,
        type_: Literal["IPv4Address", "IPv6Address"] | None = None,
        parent_id: str | int | None = None,
        name: str | None = None,
        comment: str = "Address created by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
        create_reverse_record: bool = True,
        **kwargs,
    ) -> ts.IPv4Address | ts.IPv6Address:
        json = kwargs.pop("json", {})
        if parent_id is None:
            parent_id = self.find_parent_network(address)["id"]
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

        try:
            res = self.post(url, json=json, comment=comment, **kwargs).json()
        except RESTAPIError as e:
            print(e)
            exit()

            # if state == "GATEWAY" and type_ == "IPv4Address":
            # bluecat automatically creates a blank gateway address for each IPv4 network
            # and does not allow you to manually create your own.
            # we can achieve the desired effect by fetching and updating the existing gateway address
            # this is a workaround for the bluecat API's limitations
            gw_id = self.get(url, params=dict(limit=1, filter="state:'GATEWAY'")).json()["data"][0]["id"]
            res = self.put(f"/addresses/{gw_id}", json=json, comment="Testing", **kwargs).json()  # pyright: ignore[reportArgumentType]

        return res

    def update_address(
        self,
        address_id: str | int,
        name: str | None = None,
        comment: str = "Address updated by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
        create_reverse_record: bool | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Update an existing address in Bluecat.
        Args:
            address_id (str | int): The ID of the address to update.
            name (str | None): The new name for the address.
            comment (str): A comment for the change control.
            state (IPAddressState | None): The new state of the address.
            create_reverse_record (bool | None): Whether to create a reverse record.
            **kwargs: Additional keyword arguments to pass to the request.
        Returns:
            dict[str, Any]: The updated address object.
        """
        json = kwargs.setdefault("json", {})
        if name:
            json["name"] = name
        if state:
            json["state"] = state
        if create_reverse_record is not None:
            kwargs.setdefault("headers", {})["x-bcn-create-reverse-record"] = str(create_reverse_record).lower()
        return self.put(f"/addresses/{address_id}", comment=comment, **kwargs).json()

    def create_host_record(
        self,
        name: str,
        address_id: int,
        zone_id: int,
        comment: str = "Host record created by uoft_bluecat tool",
    ):
        json = ts.hostrecord_post(
            name=name,
            addresses=[{"id": address_id}],
            type="HostRecord",
        )
        return self.post(
            f"/zones/{zone_id}/resourceRecords",
            json=json,  # pyright: ignore[reportArgumentType]
            comment=comment,
        ).json()

    def create_address_and_host(
        self,
        ip_address: IPAddress,
        name: str,
        dns_zone: str = "netmgmt.utsc.utoronto.ca",
        comment: str = "Address and host record created by uoft_bluecat tool",
        state: IPAddressState = "STATIC",
    ):
        logger.info(f"Creating address {ip_address} with name {name} in zone {dns_zone}")
        address = self.create_address(ip_address, name=name, state=state, comment=comment)
        zone = self.get("/zones", params=dict(filter=f"absoluteName:eq('{dns_zone}')")).json()['data'][0]
        res = self.create_host_record(name, address["id"], zone["id"], comment=comment)
        return res

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
