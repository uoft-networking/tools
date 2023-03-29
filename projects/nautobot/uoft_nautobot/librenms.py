from typing import Literal, List

from uoft_core import BaseSettings
from pydantic import AnyHttpUrl, SecretStr
from requests import Session
import urllib3


class Settings(BaseSettings):
    url: AnyHttpUrl
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "librenms"


class LibreNMSRESTAPIError(Exception):
    pass


class LibreNMSRESTAPIClient:
    def __init__(self, host, token, ssl_verify=False) -> None:
        self.host = host
        self.session = Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Auth-Token": token,
            }
        )

        # pylint: disable=no-member
        # LibreNMS installation may have a self-signed cert, and cannot be verified
        if not ssl_verify:
            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore

    @property
    def alerts(self):
        url_ = f"{self.host}/api/v0/alerts"

        class Alerts:

            url = url_

            @staticmethod
            def list():
                """
                List all alerts.
                """
                return self.session.get(url_)

            @staticmethod
            def get(alert: int):
                """
                Get details of a given alert.

                :param alert: Alert ID
                """
                return self.session.get(f"{url_}/{alert}")

            @staticmethod
            def ack(alert: int):
                """
                Get details of a given alert.

                :param alert: Alert ID
                """
                return self.session.put(f"{url_}/{alert}")

            @staticmethod
            def unmute(alert: int):
                """
                Get a list of alert rules.
                """
                return self.session.put(f"{url_}/unmute/{alert}")


        return Alerts

    @property
    def alert_rules(self):
        url_ = f"{self.host}/api/v0/rules"

        class AlertRules:

            url = url_

            @staticmethod
            def list():
                """
                Get a list of alert rules.
                """
                return self.session.get(url_)

            @staticmethod
            def get(rule: int):
                """
                Get details of a given alert rule.

                :param rule: Rule ID
                """
                return self.session.get(f"{url_}/{rule}")

            @staticmethod
            def add(name: str, devices: List, builder: str, severity: Literal["ok", "warning", "critical"], disabled: int, count: int, delay: str, interval: str, mute: bool, invert: bool):
                """
                Add a new alert rule.

                :param name: This is the name of the rule and is mandatory.
                :param devices: This is either an array of device ids or -1 for a global rule
                :param builder: The rule which should be in the format entity.condition value (i.e devices.status != 0 for devices marked as down). It must be json encoded in the format rules are currently stored.
                :param severity: The severity level the alert will be raised against, Ok, Warning, Critical.
                :param disabled: Whether the rule will be disabled or not, 0 = enabled, 1 = disabled
                :param count: This is how many polling runs before an alert will trigger and the frequency.
                :param delay: Delay is when to start alerting and how frequently. The value is stored in seconds but you can specify minutes, hours or days by doing 5 m, 5 h, 5 d for each one.
                :param interval: How often to re-issue notifications while this alert is active,0 means notify once.The value is stored in seconds but you can specify minutes, hours or days by doing 5 m, 5 h, 5 d for each one.
                :param mute: If mute is enabled then an alert will never be sent but will show up in the Web UI (true or false).
                :param invert: This would invert the rules check.
                """
                data = {
                    "name": name,
                    "devices": devices,
                    "builder": builder,
                    "severity": severity,
                    "disabled": disabled,
                    "count": count,
                    "delay": delay,
                    "interval": interval,
                    "mute": mute,
                    "invert": invert,
                }
                return self.session.post(url_, json=data)

            @staticmethod
            def edit(rule_id: int, devices: List, builder: str, severity: Literal["ok", "warning", "critical"], disabled: int, count: int, delay: str, interval: str, mute: bool, invert: bool):
                """
                Edit an existing alert rule

                :param rule_id: You must specify the rule_id to edit an existing rule, if this is absent then a new rule will be created.
                :param devices: This is either an array of device ids or -1 for a global rule
                :param builder: The rule which should be in the format entity.condition value (i.e devices.status != 0 for devices marked as down). It must be json encoded in the format rules are currently stored.
                :param severity: The severity level the alert will be raised against, Ok, Warning, Critical.
                :param disabled: Whether the rule will be disabled or not, 0 = enabled, 1 = disabled
                :param count: This is how many polling runs before an alert will trigger and the frequency.
                :param delay: Delay is when to start alerting and how frequently. The value is stored in seconds but you can specify minutes, hours or days by doing 5 m, 5 h, 5 d for each one.
                :param interval: How often to re-issue notifications while this alert is active,0 means notify once.The value is stored in seconds but you can specify minutes, hours or days by doing 5 m, 5 h, 5 d for each one.
                :param mute: If mute is enabled then an alert will never be sent but will show up in the Web UI (true or false).
                :param invert: This would invert the rules check.
                """
                data = {
                    "rule_id": rule_id,
                    "devices": devices,
                    "builder": builder,
                    "severity": severity,
                    "disabled": disabled,
                    "count": count,
                    "delay": delay,
                    "interval": interval,
                    "mute": mute,
                    "invert": invert,
                }
                return self.session.post(url_, json=data)
            
            @staticmethod
            def delete(rule_id: int):
                """
                Delete an existing alert rule

                :param rule_id: You must specify the rule_id to delete an existing rule.
                """
                return self.session.delete(f"{url_}/{rule_id}")

    @property
    def devices(self):
        url = f"{self.host}/api/v0/devices"

        class Devices:
            @staticmethod
            def del_device(device: str):
                """
                Delete a given device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.delete(f"{url}/{device}")

            @staticmethod
            def get_device(device: str):
                """
                Get details of a given device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}")

            @staticmethod
            def discover_device(device: str):
                """
                Trigger a discovery of given device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/discover")

            @staticmethod
            def availability(device: str):
                """
                Get calculated availabilities of given device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/availability")

            @staticmethod
            def outages(device: str):
                """
                Get detected outages of given device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/outages")

            @staticmethod
            def get_graphs(device: str):
                """
                Get a list of available graphs for a device, this does not include ports.

                :param device:  Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/graphs")

            @staticmethod
            def list_available_health_graphs(
                device: str,
                health_type: str | None = None,
                sensor_id: int | None = None,
            ):
                """
                This function allows to do three things:
                - Get a list of overall health graphs available.
                - Get a list of health graphs based on provided class.
                - Get the health sensors information based on ID.

                :param device: Can be either device hostname or ID
                :param health_type: Optional health type / sensor class
                :param sensor_id: Optional sensor ID to retrieve specific information
                """
                if health_type:
                    if sensor_id:
                        return self.session.get(
                            f"{url}/{device}/health/{health_type}/{sensor_id}"
                        )
                    return self.session.get(f"{url}/{device}/health/{health_type}")
                return self.session.get(f"{url}/{device}/health")

            @staticmethod
            def list_available_wireless_graphs(
                device: str,
                wireless_type: str | None = None,
                sensor_id: int | None = None,
            ):
                """
                This function allows to do three things:
                - Get a list of overall wireless graphs available.
                - Get a list of wireless graphs based on provided class.
                - Get the wireless sensors information based on ID.

                :param device: Can be either device hostname or ID
                :param wireless_type: Optional wireless type / wireless class
                :param sensor_id:a Optional sensor ID to retrieve specific information
                """
                if wireless_type:
                    if sensor_id:
                        return self.session.get(
                            f"{url}/{device}/wireless/{wireless_type}/{sensor_id}"
                        )
                    return self.session.get(f"{url}/{device}/wireless/{wireless_type}")
                return self.session.get(f"{url}/{device}/wireless")

            @staticmethod
            def get_health_graph(
                device: str, health_type: str, sensor_id: int | None = None
            ):
                """
                Get a particular health class graph for a device.
                If you provide a sensor_id as well then a single sensor graph will be provided.
                If no sensor_id value is provided then you will be sent a stacked sensor graph.

                :param device: Can be either device hostname or ID
                :param health_type: Health graph as returned by list_available_health_graphs()
                :param sensor_id: Optional sensor ID graph to return from health graph
                """
                if sensor_id:
                    return self.session.get(
                        f"{url}/{device}/graphs/health/{health_type}/{sensor_id}"
                    )
                return self.session.get(f"{url}/{device}/graphs/health/{health_type}")

            @staticmethod
            def get_wireless_graph(
                device: str, graph_type: str, senor_id: int | None = None
            ):
                """
                Get a particular wireless class graph for a device.
                If you provide a sensor_id as well then a single sensor graph will be provided.
                If no sensor_id value is provided then you will be sent a stacked wireless graph.

                :param device: Can be either device hostname or ID
                :param graph_type: Name of wireless graph as returned by list_available_wireless_graphs()
                :param senor_id: Optional sensor ID graph to return from wireless sensor graph
                """
                if senor_id:
                    return self.session.get(
                        f"{url}/{device}/graphs/wireless/{graph_type}"
                    )
                return self.session.get(
                    f"{url}/{device}/graphs/wireless/{graph_type}/{senor_id}"
                )

            @staticmethod
            def get_graph_generic_by_hostname(  # pylint: disable=R0913
                device: str,
                graph_type: str,
                date_from: str | None = None,
                date_to: str | None = None,
                width: int | None = None,
                height: int | None = None,
                output: str | None = None,
            ):
                """
                Get a specific graph for a device, this does not include ports.

                :param device: Can be either device hostname or ID
                :param graph_type: Type of graph to use. Use get_graphs() to see available graphs.
                :param date_from: date you would like the graph to start
                :param date_to: date you would like the graph to end
                :param width: graph width, defaults to 1075.
                :param height: graph height, defaults to 300.
                :param output: how the graph should be outputted (base64, display), defaults to display.
                """
                parameters = dict(
                    {
                        "from": date_from,
                        "to": date_to,
                        "width": width,
                        "height": height,
                        "output": output,
                    }
                )
                return self.session.get(
                    f"{url}/{device}/{graph_type}", params=parameters
                )

            @staticmethod
            def get_port_graphs(device: str, columns: str | None = None):
                """
                Get a list of ports for a particular device.

                :param device: Can be either the device hostname or ID
                :param columns: Comma separated list of columns you want returned.
                """
                parameters = dict({"columns": columns})
                return self.session.get(f"{url}/{device}/ports", params=parameters)

            @staticmethod
            def get_device_fdb(device: str):
                """
                Get a list of FDB entries associated with a device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/fdb")

            @staticmethod
            def get_device_ip_addresses(device: str):
                """
                Get a list of IP addresses (v4 and v6) associated with a device.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/ip")

            @staticmethod
            def get_port_stack(device: str):
                """
                Get a list of port mappings for a device.
                This is useful for showing physical ports that are in a virtual port-channel.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/port_stack")

            @staticmethod
            def get_components(  # pylint: disable=R0913
                device: str,
                filter_type: str | None = None,
                component_id: int | None = None,
                label=None,
                status=None,
                disabled=None,
                ignore=None,
            ):
                """
                Get a list of components for a particular device.

                :param device: Can be either the device hostname or ID
                :param filter_type: Filter the result by type (Equals)
                :param component_id: Filter the result by id (Equals)
                :param label: Filter the result by label (Contains)
                :param status: Filter the result by status (Equals)
                :param disabled: Filter the result by disabled (Equals)
                :param ignore: Filter the result by ignore (Equals)
                """
                parameters = dict(
                    {
                        "type": filter_type,
                        "id": component_id,
                        "label": label,
                        "status": status,
                        "disabled": disabled,
                        "ignore": ignore,
                    }
                )
                return self.session.get(f"{url}/{device}/components", params=parameters)

            @staticmethod
            def add_components(device: str, component_type: str):
                """
                Create a new component of a type on a particular device.

                :param device: Can be either the device hostname or ID
                :param component_type: Type of component to add
                """
                return self.session.post(f"{url}/{device}/components/{component_type}")

            @staticmethod
            def edit_components(  # pylint: disable=R0913
                device: str,
                component_id: int,
                component_type: str | None = None,
                label: str | None = None,
                status: int | None = None,
                ignore: int | None = None,
                disabled: int | None = None,
                error: str | None = None,
            ):
                """
                Edit an existing component on a particular device.

                :param device: Can be either the decice hostname or ID
                :param component_id:
                :param component_type:
                :param label:
                :param status:
                :param ignore:
                :param disabled:
                :param error:
                """
                data = dict(
                    {
                        component_id: {
                            "type": component_type,
                            "label": label,
                            "status": status,
                            "ignore": ignore,
                            "disabled": disabled,
                            "error": error,
                        }
                    }
                )
                return self.session.put(f"{url}/{device}/components", data)

            @staticmethod
            def delete_components(device: str, component: int):
                """
                Delete an existing component on a particular device.

                :param device: Can be either the device hostname or ID
                :param component: Component ID to be deleted
                """
                return self.session.delete(
                    f"{url}/{device}/components/{component}",
                )

            @staticmethod
            def get_port_stats_by_port_hostname(
                device: str, interface_name: str, columns: str | None = None
            ):
                """
                Get information about a particular port for a device.

                :param device: Can be either the device hostname or ID
                :param interface_name: Any of the interface names for the device which can be obtained using get_port_graphs.
                Please ensure that the ifname is urlencoded if it needs to be (i.e Gi0/1/0 would need to be urlencoded.
                :param columns: Comma separated list of columns you want returned
                """
                parameters = dict({"columns": columns})
                interface_name = interface_name.replace("/", "%2F")
                return self.session.get(
                    f"{url}/{device}/ports/{interface_name}", params=parameters
                )

            @staticmethod
            def get_graph_by_port_hostname(  # pylint: disable=R0913
                device: str,
                interface_name: str,
                port_type: str,
                date_from: str | None = None,
                date_to: str | None = None,
                width: int | None = None,
                height: int | None = None,
                interface_description: bool | None = None,
            ):
                """
                Get a graph of a port for a particular device.

                :param device: Can be either the device hostname or ID
                :param interface_name: Any of the interface names for the device which can be
                    obtained using get_port_graphs.
                Please ensure that the ifname is urlencoded if it needs to be (i.e Gi0/1/0 would need to be urlencoded.
                :param port_type: Type is the port type you want the graph for.
                You can request a list of ports for a device with get_port_graphs
                :param date_from: date you would like the graph to start
                :param date_to: date you would like the graph to end
                :param width: graph width, defaults to 1075.
                :param height: graph height, defaults to 300.
                :param interface_description: Will use ifDescr to lookup the port instead of ifName when true.
                Pass the ifDescr value you want to search as you would ifName.
                """
                parameters = dict(
                    {
                        "from": date_from,
                        "to": date_to,
                        "width": width,
                        "height": height,
                        "ifDescr": interface_description,
                    }
                )
                interface_name = interface_name.replace("/", "%2F")
                return self.session.get(
                    f"{url}/{device}/ports/{interface_name}/{port_type}",
                    params=parameters,
                )

            @staticmethod
            def list_locations():
                """Return a list of locations."""
                return self.session.get(f"{self.host}/api/v0/resources/locations")

            @staticmethod
            def list_sensors():
                """Get a list of all Sensors."""
                return self.session.get(f"{self.host}/api/v0/resources/sensors")

            @staticmethod
            def list_devices(
                order: str | None = None,
                order_type: str | None = None,
                query: str | None = None,
            ):
                """
                Return a list of devices.

                === Order Types ===

                - all: All devices
                - active: Only not ignored and not disabled devices
                - ignored: Only ignored devices
                - up: Only devices that are up
                - down: Only devices that are down
                - disabled: Disabled devices
                - os: search by os type
                - mac: search by mac address
                - ipv4: search by IPv4 address
                - ipv6: search by IPv6 address
                - location: search by location
                - hostname: search by hostname

                :param order: Orders output. Defaults 'hostname'. Can be prepended by DESC or ASC to change the order
                :param order_type: Filter or search by one of the parameters shown above
                :param query: If searching by, then this will be used as the input
                """
                parameters = dict({"order": order, "type": order_type, "query": query})
                return self.session.get(url, params=parameters)

            @staticmethod
            def add_device(  # pylint: disable=C0103, R0913, R0914
                hostname: str,
                overwrite_ip: str | None = None,
                port: int | None = None,
                transport: str | None = None,
                version: str | None = None,
                poller_group: int | None = None,
                force_add: bool | None = None,
                community: str | None = None,
                authlevel: str | None = None,
                authname: str | None = None,
                authpass: str | None = None,
                authalgo: str | None = None,
                cryptopass: str | None = None,
                cryptoalgo: str | None = None,
                snmp_disable: bool | None = None,
                os: str | None = None,
                hardware: str | None = None,
            ):
                """
                Add a new device.

                :param hostname: device hostname
                :param overwrite_ip: alternate polling IP. Will be use instead of hostname (optional)
                :param port: SNMP port (defaults to port defined in config).
                :param transport: SNMP protocol (defaults to transport defined in config).
                :param version: SNMP version to use, v1, v2c or v3. Defaults to v2c.
                :param poller_group: This is the poller_group id used for distributed poller setup. Defaults to 0.
                :param force_add: Force the device to be added regardless of it being able to respond to snmp or icmp.
                :param community: Required for SNMP v1 or v2c.
                :param authlevel: SNMP authlevel (noAuthNoPriv, authNoPriv, authPriv).
                :param authname: SNMP Auth username
                :param authpass: SNMP Auth password
                :param authalgo: SNMP Auth algorithm (MD5, SHA)
                :param cryptopass: SNMP Crypto Password
                :param cryptoalgo: SNMP Crypto algorithm (AES, DES)
                :param snmp_disable: Boolean, set to true for ICMP only.
                :param os: OS short name for the device (defaults to ping).
                :param hardware: Device hardware.
                """
                data = dict(
                    {
                        "hostname": hostname,
                        "overwrite_ip": overwrite_ip,
                        "port": port,
                        "transport": transport,
                        "version": version,
                        "poller_group": poller_group,
                        "force_add": force_add,
                        "community": community,
                        "authlevel": authlevel,
                        "authname": authname,
                        "authpass": authpass,
                        "authalgo": authalgo,
                        "cryptopass": cryptopass,
                        "cryptoalgo": cryptoalgo,
                        "snmp_disable": snmp_disable,
                        "os": os,
                        "hardware": hardware,
                    }
                )
                return self.session.post(url, json=data)

            @staticmethod
            def list_oxidized(device: str | None = None):
                """
                List devices for use with Oxidized.
                If you have group support enabled then a group will also be returned based on your config.

                :param device: Can be either the device hostname or ID
                """
                if device:
                    return self.session.get(
                        f"{self.host}/api/v0/oxidized/{device}",
                    )
                return self.session.get(f"{self.host}/api/v0/oxidized")

            @staticmethod
            def update_device_field(device: str, field=None, data=None):
                """
                Updates devices field in the database.

                :param device: Can be either the device hostname or ID
                :param field: Column name within the database (can be an array of fields)
                :param data: Data to update the column with (can be an array of data)
                """
                data = dict(
                    {
                        "field": field,
                        "data": data,
                    }
                )
                return self.session.patch(f"{url}/{device}", json=data)

            @staticmethod
            def rename_device(device: str, new_hostname: str):
                """
                Rename device.

                :param device: Can be either the device hostname or ID
                :param new_hostname: New hostname for the device
                """
                return self.session.patch(f"{url}/{device}/rename/{new_hostname}")

            @staticmethod
            def get_device_groups(device: str):
                """
                List the device groups that a device is matched on.

                :param device: Can be either the device hostname or ID
                """
                return self.session.get(f"{url}/{device}/groups")

            @staticmethod
            def search_oxidized(search_string: str):
                """
                Search all oxidized device configs for a string.

                :param search_string: The Specific string you would like to search for
                """
                return self.session.get(
                    f"{self.host}/api/v0/oxidized/config/search/{search_string}"
                )

            @staticmethod
            def get_oxidized_config(device_name: str):
                """
                Returns a specific device's config from oxidized.

                :param device_name: The full DNS name of the device used when adding the device to LibreNMS
                """
                return self.session.get(
                    f"{self.host}/api/v0/oxidized/config/{device_name}"
                )

            @staticmethod
            def add_parents_to_host(device: str, parent_ids):
                """
                Add one or more parents to host.

                :param device: Can be either the device hostname or ID
                :param parent_ids: One or more parent IDs or hostnames
                """
                data = dict(
                    {
                        "parent_ids": parent_ids,
                    }
                )
                return self.session.post(f"{url}/{device}/parents", json=data)

            @staticmethod
            def delete_parents_from_host(device: str, parent_ids=None):
                """
                Deletes some or all of the parents from a host.

                :param device: Can be either the device hostname or ID
                :param parent_ids: One or more parent IDs or hostnames.
                If not specified deletes all parents from host.
                """
                data = dict(
                    {
                        "parent_ids": parent_ids,
                    }
                )
                return self.session.delete(f"{url}/{device}/parents", data=data)

            @staticmethod
            def maintenance_device(device: str, notes: str, duration: str):
                """
                Set a device into maintenance mode.

                :param device: Can be either the device hostname or ID
                :param notes: Some description for the Maintenance
                :param duration: Duration of Maintenance in format H:m
                """
                data = dict({"notes": notes, "duration": duration})
                return self.session.post(f"{url}/{device}/maintenance", json=data)

        return Devices

    @property
    def device_groups(self):
        url = f"{self.host}/api/v0/devicegroups"

        class DeviceGroups:
            @staticmethod
            def get_devicegroups():
                """List all device groups."""
                return self.session.get(url)

            @staticmethod
            def add_devicegroups(
                name: str,
                group_type: str,
                desc: str | None = None,
                rules: str | None = None,
                devices: list | None = None,
            ):
                """
                Add a new device group.
                Upon success, the ID of the new device group is returned and the HTTP response code is 201.

                :param name: Name of the group
                :param group_type: Should be `static` or `dynamic`.
                Setting this to static requires that the devices input be provided.
                :param desc: Description of the device group
                :param rules: required if type == dynamic.
                A set of rules to determine which devices should be included in this device group
                :param devices: required if type == static.
                A list of devices that should be included in this group. This is a static list of devices
                """
                data = dict(
                    {
                        "name": name,
                        "type": group_type,
                        "desc": desc,
                    }
                )
                if group_type == "static":
                    data.update({"devices": devices})  # type: ignore
                elif group_type == "dynamic":
                    data.update({"rules": rules})

                return self.session.post(url, json=data)

            @staticmethod
            def get_devices_by_group(name: str):
                """
                List all devices matching the group provided.

                :param name: name of the device group which can be obtained using get_devicegroups.
                Please ensure that the name is urlencoded if it needs to be (i.e Linux Servers would need to be urlencoded.
                """
                return self.session.get(f"{url}/{name}")

        return DeviceGroups

    @property
    def inventory(self):
        url = f"{self.host}/api/v0/inventory"

        class Inventory:
            @staticmethod
            def get_inventory(
                device: str,
                ent_physical_class: str | None = None,
                ent_physical_contained_in: str | None = None,
            ):
                """
                Retrieve the inventory for a device.
                If you call this without any parameters then you will only get part of the inventory.
                This is because a lot of devices nest each component.
                For instance you may initially have the chassis,
                within this the ports - 1 being an SFP cage, then the SFP itself.
                The way this API call is designed is to enable a recursive lookup.
                The first call will retrieve the root entry, included within this response will be entPhysicalIndex.
                You can then call for entPhysicalContainedIn which will then return the next layer of results.
                To retrieve all items together, see get_inventory_for_device.

                :param device: Can be either the device hostname or ID
                :param ent_physical_class: Used to restrict the class of the inventory.
                For example you can specify chassis to only return items in the inventory that are labelled as chassis.
                :param ent_physical_contained_in: Used to retrieve items within the inventory assigned to a previous component.
                For example specifying the chassis (entPhysicalIndex) will retrieve all items where the chassis is the parent.
                """
                parameters = dict(
                    {
                        "entPhysicalClass": ent_physical_class,
                        "entPhysicalContainedIn": ent_physical_contained_in,
                    }
                )
                return self.session.get(f"{url}/{device}", params=parameters)

            @staticmethod
            def get_inventory_for_device(
                device: str,
                ent_physical_class: str | None = None,
                ent_physical_contained_in: str | None = None,
            ):
                """
                Retrieve the flattened inventory for a device.
                This retrieves all inventory items for a device regardless of their structure,
                and may be more useful for devices with with nested components.

                :param device: Can be either the device hostname or ID
                :param ent_physical_class: Used to restrict the class of the inventory.
                For example you can specify chassis to only return items in the inventory that are labelled as chassis.
                :param ent_physical_contained_in: Used to retrieve items within the inventory assigned to a previous component.
                For example specifying the chassis (entPhysicalIndex) will retrieve all items where the chassis is the parent.
                """
                parameters = dict(
                    {
                        "entPhysicalClass": ent_physical_class,
                        "entPhysicalContainedIn": ent_physical_contained_in,
                    }
                )
                return self.session.get(f"{url}/{device}/all", params=parameters)

        return Inventory

    @property
    def locations(self):
        url = f"{self.host}/api/v0/locations"

        class Locations:
            @staticmethod
            def add_location(location: str, lat=None, lng=None):
                """
                Add a new location.

                :param location: Name of the new location
                :param lat: Latitude
                :param lng: Longitude
                """
                data = dict(
                    {
                        "location": location,
                        "lat": lat,
                        "lng": lng,
                    }
                )
                return self.session.post(url, json=data)

            @staticmethod
            def delete_location(location: str):
                """
                Deletes an existing location.

                :param location: Name of the location to delete
                """
                return self.session.delete(f"{url}/{location}")

            @staticmethod
            def edit_location(location: str, lat=None, lng=None):
                """
                Edits a location.

                :param location: Name of the location to edit
                :param lat: Latitude
                :param lng: Longitude
                """
                data = dict(
                    {
                        "lat": lat,
                        "lng": lng,
                    }
                )
                return self.session.patch(f"{url}/{location}", json=data)

        return Locations

    @property
    def ports(self):
        url = f"{self.host}/api/v0/ports"

        class Ports:
            @staticmethod
            def get_all_ports(columns: list[str] | None = None):
                """
                Get info for all ports on all devices.
                Strongly recommend that you use the columns parameter to avoid pulling too much data.

                :param columns: list of column names to return for each port, ex: `["ifName", "ifDescr", "port_id"]`.
                """
                if columns is None:
                    columns = ["ifName", "port_id"]
                parameters = dict({"columns": columns})
                return self.session.get(url, params=parameters)

            @staticmethod
            def search_ports(search_for: str, columns: list[str] | None = None):
                """
                Search for ports by name, alias, or description.

                :param search_for: The string to search for
                :param columns: list of column names to return for each port, ex: `["ifName", "ifDescr", "port_id"]`.
                """
                if columns is None:
                    columns = ["ifName", "port_id"]
                parameters = dict({"columns": columns})
                return self.session.get(f"{url}/search/{search_for}", params=parameters)

            @staticmethod
            def search_ports_by(
                search_for: str,
                search_in: list[str] | None = None,
                columns: list[str] | None = None,
            ):
                """
                Search for ports matching query.
                Search for ports which contain the `search_for` string in any of the fields in the `search_in` list.

                :param search_for: The string to search for
                :param search_in: list of column names to search in, ex: `["ifName", "ifAlias", "ifDescr"]`.
                :param columns: list of column names to return for each port, ex: `["ifName", "ifDescr", "port_id"]`.
                """
                if columns is None:
                    columns = ["ifName", "port_id"]
                if search_in is None:
                    search_in = ["ifName"]
                parameters = dict({"columns": columns})
                return self.session.get(f"{url}/search/{search_in}/{search_for}", params=parameters)

        return Ports
