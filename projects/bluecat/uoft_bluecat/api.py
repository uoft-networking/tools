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
    def __init__(
        self, base_url: str, username: str, password: str, configuration: str | None = None, verify: bool | str = True
    ):
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
        # tok_data contains an apiToken field. You would think that the api token would be a valid Bearer token,
        # but it's not. Using it as such produces a 401 error. Thanks bluecat!
        # token = tok_data['apiToken']
        # tok_data also contains a basicAuthenticationCredentials field
        # which is a base64 encoded string of the form "username:token"
        # and THAT is what we need to use to authenticate
        credentials = token_response["basicAuthenticationCredentials"]
        self.headers.update({
            "Authorization": f"Basic {credentials}",
        })
        super().login()

    def logout(self):
        # Bluecat REST V2 API does not have a logout endpoint
        pass

    def get(self, url, params: dict[str, Any] | None = None, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        if params and 'skip_configuration_filtering' in params:
            # explicitly skip configuration filtering
            del params['skip_configuration_filtering']
        elif self.configuration:
            # add configuration filter if not already set
            if not params or "filter" not in params:
                params = params or {}
                params["filter"] = f"configuration.id:eq({self.configuration_id})"
            elif "configuration.id:" not in params["filter"]:
                params["filter"] = f"configuration.id:eq({self.configuration_id}) and {params['filter']}"
        
        try:
            return super().get(url, params=params, **kwargs)
        except RESTAPIError as e:
            # re-raise here so debugger stops here instead of stopping deep in the bowels of the requests machinery
            raise e

    def put(self, url: str, comment: str, json: dict | list, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        # bluecat `PUT` methods require so many bits of information from the source record, that it's
        # easier to just fetch the original record being updated and merge the new data into it
        original = self.get(url, params=dict(skip_configuration_filtering=True)).json()
        if isinstance(json, list):
            new_data = []
            for item in json:
                item = {**original, **item}
                new_data.append(item)
            json = new_data
        elif isinstance(json, dict):
            json = {**original, **json}
        else:
            raise TypeError(f"json must be a dict or list, not {type(json)}")
        try:
            return super().put(url, json=json, **kwargs)
        except RESTAPIError as e:
            # re-raise here so debugger stops here instead of stopping deep in the bowels of the requests machinery
            raise e

    def post(self, url: str, comment: str, data: Any = None, json: dict | list | None = None, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        if self.configuration:
            if isinstance(json, list):
                for item in json:
                    item.setdefault("configuration", {"id": self.configuration_id})
            elif isinstance(json, dict):
                json.setdefault("configuration", {"id": self.configuration_id})
        return super().post(url, data, json=json, **kwargs)

    def delete(self, url: str, comment: str, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        # Every change in bluecat requires a comment
        headers = kwargs.setdefault("headers", {})
        headers["x-bcn-change-control-comment"] = comment
        try:
            return super().delete(url, **kwargs)
        except RESTAPIError as e:
            # re-raise here so debugger stops here instead of stopping deep in the bowels of the requests machinery
            raise e

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
        if self.configuration is None:
            # old behaviour, kept around for compatability
            logger.warning("No configuration specified, using the first configuration found")
            return self.get(self.api_url / "configurations").json()["data"][0]["id"]
        # get the configuration ID by name
        configurations = (
            super()
            .get(self.api_url / "configurations", params=dict(filter=f"name:eq('{self.configuration}')"))
            .json()["data"]
        )
        if not configurations:
            raise ValueError(f"Configuration '{self.configuration}' not found")
        if len(configurations) > 1:
            raise ValueError(f"Multiple configurations found with name '{self.configuration}'")
        return configurations[0]["id"]

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
    def get_address(self, address: str | IPAddress, **kwargs) -> ts.IPv4Address | ts.IPv6Address:
        """
        Get an address by its IP.

        Args:
            address (str | IPAddress): The IP address to search for.
            **kwargs: Additional keyword arguments to pass to the request.
        """
        res = self.get(
            "/addresses",
            params=dict(filter=f"address:eq('{address}')"),
            **kwargs,
        ).json()
        if res["count"] == 0:
            raise ValueError(f"Address {address} not found")
        if res["count"] > 1:
            raise ValueError(f"Multiple addresses found for {address}")
        return res["data"][0]

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
            if state == "GATEWAY" and type_ == "IPv4Address":
                # bluecat automatically creates a blank gateway address for each IPv4 network
                # and does not allow you to manually create your own.
                # we can achieve the desired effect by fetching and updating the existing gateway address
                # this is a workaround for the bluecat API's limitations
                gw_id = self.get(url, params=dict(limit=1, filter="state:'GATEWAY'")).json()["data"][0]["id"]
                res = self.put(
                    f"/addresses/{gw_id}", json=json, comment="GW updated by uoft_bluecat tool", **kwargs
                ).json()  # pyright: ignore[reportArgumentType]
            else:
                raise e

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
        json = kwargs.pop("json", {})
        if name:
            json["name"] = name
        if state:
            json["state"] = state
        if create_reverse_record is not None:
            kwargs.setdefault("headers", {})["x-bcn-create-reverse-record"] = str(create_reverse_record).lower()
        try:
            return self.put(f"/addresses/{address_id}", json=json, comment=comment, **kwargs).json()
        except RESTAPIError as e:
            if e.data and "code" in e.data and e.data["code"] == "CreateUpdateNetworkGatewayNotSupported":
                # Can't modify the state of a gatewy address
                del json["state"]
                # Try again
                return self.put(f"/addresses/{address_id}", json=json, comment=comment, **kwargs).json()
            raise e

    def get_zone(self, dns_zone: str, **kwargs):
        params = kwargs.pop("params", {})
        params["filter"] = f"absoluteName:eq('{dns_zone}') and type:eq('Zone')"
        res = self.get(
            "/zones",
            params=params,
            **kwargs,
        ).json()
        if res["count"] == 0:
            raise ValueError(f"Zone {dns_zone} not found")
        if res["count"] > 1:
            raise ValueError(f"Multiple zones found for {dns_zone}")
        return res["data"][0]

    def create_zone(
        self, dns_zone: str, view_id: int | None = None, comment: str = "Zone created by uoft_bluecat tool", **kwargs
    ):
        """
        Create a new DNS zone in Bluecat.

        Args:
            dns_zone (str): The name of the DNS zone to create.
            view_id (int): The ID of the view to associate with the zone.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The created zone object.
        """
        if not view_id:
            # If no view_id is provided, use the default view for the configuration
            views = self.get(f"/configurations/{self.configuration_id}/views").json()["data"]
            if len(views) == 0:
                raise ValueError(f"No views found for configuration {self.configuration_id}")
            view_id = views[0]["id"]
        json = kwargs.pop("json", {})
        json["absoluteName"] = dns_zone
        json["type"] = "Zone"
        json = ts.zone_post(**json)
        return self.post(f"/views/{view_id}/zones", json=json, comment=comment, **kwargs).json()  # pyright: ignore[reportArgumentType]

    def update_zone(
        self, zone_id: int, json: dict[str, Any], comment: str = "Zone updated by uoft_bluecat tool", **kwargs
    ):
        """
        Update an existing zone in Bluecat.

        Args:
            zone_id (int): The ID of the zone to update.
            json (dict[str, Any]): The JSON data to update the zone with.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The updated zone object.
        """
        return self.put(f"/zones/{zone_id}", json=json, comment=comment, **kwargs).json()

    def get_host_record(self, absolute_name: str, **kwargs):
        params = kwargs.pop("params", {})
        params["filter"] = f"absoluteName:eq('{absolute_name}')"
        res = self.get(
            "/resourceRecords",
            params=params,
            **kwargs,
        ).json()
        if res["count"] == 0:
            raise ValueError(f"Host record {absolute_name} not found")
        if res["count"] > 1:
            raise ValueError(f"Multiple host records found for {absolute_name}")
        return res["data"][0]

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
        try:
            return self.post(
                f"/zones/{zone_id}/resourceRecords",
                json=json,  # pyright: ignore[reportArgumentType]
                comment=comment,
            ).json()
        except RESTAPIError as e:
            if e.response.status_code == 409 and "Duplicated with a zone name." in e.data.get("detail", ""):
                raise ValueError(f"There is a sub-zone with this name that must be removed first")
            raise e

    def update_host_record(
        self,
        record_id: int,
        record: dict[str, Any],
        comment: str = "Host record updated by uoft_bluecat tool",
        **kwargs,
    ):
        """
        Update an existing host record in Bluecat.

        Args:
            record_id (int): The ID of the host record to update.
            record (dict[str, Any]): The updated host record data.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The updated host record object.
        """
        return self.put(f"/resourceRecords/{record_id}", json=record, comment=comment, **kwargs).json()

    def delete_host_record(self, record_id: int, comment: str = "Host record deleted by uoft_bluecat tool", **kwargs):
        """
        Delete an existing host record in Bluecat.

        Args:
            record_id (int): The ID of the host record to delete.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The response from the delete operation.
        """
        return self.delete(f"/resourceRecords/{record_id}", comment=comment, **kwargs)

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

    def update_network(
        self, id: int, json: dict[str, Any], comment: str = "Network updated by uoft_bluecat tool", **kwargs
    ):
        """
        Update an existing network in Bluecat.

        Args:
            id (int): The ID of the network to update.
            json (dict[str, Any]): The JSON data to update the network with.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The updated network object.
        """
        return self.put(f"/networks/{id}", json=json, comment=comment, **kwargs).json()

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

    def update_block(
        self, id: int, json: dict[str, Any], comment: str = "Block updated by uoft_bluecat tool", **kwargs
    ):
        """
        Update an existing block in Bluecat.

        Args:
            id (int): The ID of the block to update.
            json (dict[str, Any]): The JSON data to update the block with.
            comment (str): A comment for the change control.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            dict[str, Any]: The updated block object.
        """
        return self.put(f"/blocks/{id}", json=json, comment=comment, **kwargs).json()

    def get_dns_servers(self, **kwargs):
        # bluecat does not support filtering servers by state (eg ENABLED) or by profile (eg DNS_DHCP_SERVER_*)
        # so we have to fetch all servers and filter them ourselves
        params = kwargs.pop("params", {})
        params['fields'] = 'embed(deploymentRoles)'
        all_servers = self.get(
            "/servers",
            params=params,
            **kwargs,
        ).json()['data']
        dns_servers = [s for s in all_servers if 'DNS_DHCP_SERVER_' in s['profile'] and s['state'] == 'ENABLED']
        if len(dns_servers) == 0:
            raise ValueError("No enabled DNS/DHCP servers found")
        return dns_servers

    def deploy_changes(
        self,
        server_id: int,
        service: Literal["DHCPv4", "DNS"],
        comment: str = "Deploy changes by uoft_bluecat tool",
        **kwargs,
    ):
        payload = dict(type="FullDeployment", service=service)
        return self.post(
            f"/servers/{server_id}/deployments", json=payload, comment=comment, **kwargs
        ).json()

    def deployment_status(self, deployment_id: int, **kwargs):
        params = kwargs.pop("params", {})
        params['skip_configuration_filtering'] = True
        return self.get(f"/deployments/{deployment_id}", params=params, **kwargs).json()
