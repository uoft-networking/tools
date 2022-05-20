# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module for the client to work with BlueCat Address Manager's API."""
# pylint: disable=too-many-lines,redefined-builtin
# pylint: disable=E1101,C0112,C0115,C0116,W0511,W0612,W0613,E1120;
import json
from typing import Any, Optional, Union, List, IO

from .models import (
    APIEntity,
    APIUserDefinedField,
    UDLDefinition,
    UDLRelationship,
    APIAccessRight,
    APIDeploymentRole,
    RetentionSettings,
    APIDeploymentOption,
    ResponsePolicySearchResult,
    APIData,
)
from .rest.auto.client import Client as RawClient
from .rest.auto import _wadl_parser
from .serialization import (
    deserialize_joined_key_value_pairs,
    serialize_joined_key_value_pairs,
    serialize_joined_values,
    serialize_possible_list,
)
from ._version import Version as _Version
from ..constants import _version
from ..constants.numeric import DEFAULT_COUNT
from ...http_client import ClientError, ErrorResponse

__all__ = [
    "Client",
]


class Client:
    """BAM API Client"""

    def __init__(self, url: str, *, verify: Any = True) -> None:
        """Construct using a url"""
        self._raw_api = RawClient(url, verify=verify)

    def close(self):
        """Release any allocated resources, e.g., an internal session."""
        self._raw_api.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def is_authenticated(self) -> bool:
        """
        Determine whether the authentication necessary to communicate with the target service is
        set.
        """
        return self._raw_api.is_authenticated

    def _require_auth(self):
        """
        Raise exception if the client does not have the necessary authentication
        set to communicate with the target service.
        """
        if not self.is_authenticated:
            raise ClientError("Use of this method requires authentication.")

    @property
    def raw_api(self) -> RawClient:
        return self._raw_api

    # region BAM Version
    # pylint: disable=protected-access

    @property
    def system_version(self) -> Optional[str]:
        """
        Version of the BlueCat Address Manager the client is connected to. Return value
        ``None`` means this client has never been logged into.

        :return: Version of BlueCat Address Manager.
        :rtype: Optional[str]
        """
        v = self._raw_api._service.version
        return str(v) if v else None

    def _require_minimal_version(self, version: Union[_Version, str]) -> None:
        """
        Raise exception if the Address Manager version is not equal or greater than a required one.

        :param version: Required minimal version.
        :type version: Version | str
        :raise: ClientError
        """
        v = self._raw_api._service.version
        if v and v < version:
            raise ClientError(f"The Address Manager version must be {version} or greater.")

    # endregion BAM Version

    # region Authentication

    def login(self, username, password):
        return self._raw_api.login(username, password)

    def login_with_options(self, username, password, options):
        """
        Log user into BAM with additional options
        - locale: option to indicate the locale
        - isReadOnly: option to initiate a read only api session

        :param username: Username
        :type username: str
        :param password: Password
        :type password: str
        :param options: The options for login
        :type options: dict

        .. note:: isReadOnly is available with BAM 9.3 or greater
        """
        options = serialize_joined_key_value_pairs(options)
        return self._raw_api.loginWithOptions(username, password, options)

    def logout(self):
        self._require_auth()
        return self._raw_api.logout()

    def set_token(self, token):
        self._raw_api.set_token(token)

    # endregion Authentication

    # region System information

    def get_system_info(self):
        """
        Get Address Manager system information.

        :return: Address Manager system information.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    data = client.get_system_info()

                for key, value in data.items():
                    print('{}: {}'.format(key, value))

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        data = self._raw_api.getSystemInfo()
        data = deserialize_joined_key_value_pairs(data)
        return data

    # endregion System information

    # region Entity

    def add_entity(self, parent_id: int, entity: APIEntity) -> int:
        """
        Add an entity object.

        :param parent_id: The ID of the object that will be parent to the added entity.
        :type parent_id: int
        :param entity: The entity to add. Its fields should be structured as per
        :type entity: APIEntity
        :return: The ID of the added entity object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIEntity

                props = {
                    udf1_name: 'udf1_value',
                    udf2_name: 'udf2_value',
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = APIEntity(name='config', type='Configuration', properties=props)
                    client.add_entity(<parent_id>, entity)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        return self.raw_api.addEntity(parent_id, APIEntity.to_raw_model(entity))

    def update_entity(self, entity: APIEntity):
        """
        Update an entity object.

        :param entity: The actual API entity passed as an entire object that has its mutable values updated.
        :type entity: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_entity_by_id(<entity_id>)
                    entity['name'] = 'new name'
                    entity['properties']['configurationGroup'] = 'new group name'
                    client.update_entity(entity)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self.raw_api.update(APIEntity.to_raw_model(entity))

    def update_entity_with_options(self, entity: APIEntity, options: dict):
        """
        Update objects requiring a certain behavior that is not covered by the regular update method.
        This method applies to CNAME, MX, and SRV records, and DNS/DHCP Servers.

        :param entity: The actual API entity to update.
        :type entity: APIEntity
        :param options: A dictionary containing the update options:

            * linkToExternalHost: a String value. If the value is 'true', it will search for the external
              host record specified in linkedRecordName even if a host record with the same exists under the same
              DNS View. If the external host record is not present, it will throw an exception.
              If the value is 'false', it will search for the host record specified in linkedRecordName.
            * disable: a String value. If the value is 'true', the DNS/DHCP Server is disabled.
              Disabling a server stops all deployments, DDNS updates, and services on that server.
              If the value is 'false', the server is enabled and restores the disabled server to normal operation.
            * resetControl: a String value. If the value is 'true', the DNS/DHCP Server is removed
              from Address Manager control. Once you have removed a DNS/DHCP Server from Address Manager control,
              you must replace the server from Address Manager to reconfigure it.
        :type options: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                # Updating CNAME, MX, and SRV records
                options = {'linkToExternalHost': 'true'}
                # Updating DNS/DHCP Servers
                # options = {'disable': 'true', 'resetControl': 'true'}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_entity_by_id(<entity_id>)
                    entity['name'] = 'new name'
                    client.update_entity_with_options(entity, options)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        option = serialize_joined_key_value_pairs(options)
        self.raw_api.updateWithOptions(option, APIEntity.to_raw_model(entity))

    def delete_entity(self, id: int):
        """
        Delete an entity object.

        :param id: The ID of the entity to delete.
        :type id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_entity(<id>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self.raw_api.delete(id)

    def delete_entity_with_options(self, id: int, options: dict = None):
        """
        Delete objects that have options associated with their removal. When deleting dynamic resource records,
        you can choose not to dynamically deploy the changes to the DNS/DHCP Server.

        :param id: The ID of the object to delete.
        :type id: int
        :param options: A dictionary containing the delete options:

            * noServerUpdate: a string value. This applies to the dynamic resource records.
              The value is 'true' to update the record only in the Address Manager web interface.
              The change will not be deployed to the DNS server. The default value is 'false'.
            * deleteOrphanedIPAddresses: a string value. This applies to the delete operation on Host Records.
              The value is 'true' to free IP addresses associated with a host record if no other host records are
              associated with the IP address. The default value is 'false'.
            * removeMacFromPool: a string value. This applies to the delete operation of DHCP Reserved addresses.
              The value is 'true' to remove the MAC address of the IP address from any associated MAC pools.
              The default value is 'false'.
        :type options: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                # This applies to the dynamic resource records
                options = {'noServerUpdate': 'true'}
                # Delete operation on Host Records
                # options = {'deleteOrphanedIPAddresses': 'true'}
                # Delete operation of DHCP Reserved addresses (BAM version >= 9.3.0 is required)
                # options = {'removeMacFromPool': 'true'}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_entity_with_options(<id>, options)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        self.raw_api.deleteWithOptions(id, options)

    def get_parent(self, entity_id: int) -> APIEntity:
        """
        Get the parent entity of a given entity.

        :param entity_id: The entity ID of the child object that you would like to find its parent entity ID.
        :type entity_id: int
        :return: The APIEntity for the parent entity with its properties fields populated.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_parent(<entity_id>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entity = self.raw_api.getParent(entity_id)
        return APIEntity.from_raw_model(entity)

    def get_entity_by_id(self, id: int) -> APIEntity:
        """
        Get an entity object by its ID.

        :param id: The ID of the entity object to return.
        :type id: int
        :return: An entity object.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_entity_by_id(<id>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entity = self._raw_api.getEntityById(id)
        return APIEntity.from_raw_model(entity)

    def get_entity_by_name(self, parent_id: int, name: str, type: str) -> APIEntity:
        """
        Get objects from the database referenced by their name field.

        :param parent_id: The ID of the target object's parent object.
        :type parent_id: int
        :param name: The name of the target object.
        :type name: str
        :param type: The type of object returned by the method.
        :type type: str
        :return: An entity object.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                name = "default"
                type = ObjectType.VIEW

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_entity_by_name(<parent_id>, name, type)
                print(entity)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entity = self.raw_api.getEntityByName(parent_id, name, type)
        return APIEntity.from_raw_model(entity)

    def get_entity_by_range(
        self, parent_id: int, start_address: str, end_address: str, type: str
    ) -> APIEntity:
        """
        Get an IPv4 or IPv6 DHCP range or block object defined by its range.

        :param parent_id: The object ID of the parent object of the DHCP range.
        :type parent_id: int
        :param start_address: An IP address defining the lowest address or start of the range.
        :type start_address: str
        :param end_address: An IP address defining the highest address or end of the range.
        :type end_address: str
        :param type: The type of object returned, it must be one of the constants listed for Object types.
            For example: IP4Block, IP6Block, DHCP4Range, DHCP6Range.
        :type type: str
        :return: A range object like an IP block or a DHCP range. None if the object was not found.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                parent_id = <configuration_id>
                start_address = "10.0.0.1"
                end_address = "10.0.0.10"
                type = ObjectType.IP4_BLOCK

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    # The IP4 Block type is to be retrieved, the entity is a configuration id.
                    entity = client.get_entity_by_range(parent_id, start_address, end_address, type)
                print(entity)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(
            self.raw_api.getEntityByRange(parent_id, start_address, end_address, type)
        )

    def get_entities(
        self, parent_id: int, type: str, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of entities for a parent object.

        :param parent_id: The object ID of the parent object of the entities.
        :type parent_id: int
        :param type: The type of object to return.
        :type type: str
        :param start: Indicates where in the list of child objects to start returning entities.
            The list begins at an index of 0.
        :type start: int
        :param count: Indicates the maximum number of child objects to return. The default value is 10.
        :type count: int
        :return: A list of entities. The list is empty if there are no matching entities.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_entities(<parent_id>, ObjectType.VIEW, 0, 10)
                print(entities)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entities = self.raw_api.getEntities(parent_id, type, start, count)
        return list(map(APIEntity.from_raw_model, entities))

    def get_entities_by_name(
        self, parent_id: int, name: str, type: str, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of entities that match the specified parent, name, and object type.

        :param parent_id: The object ID of the parent object of the entities.
        :type parent_id: int
        :param name: The name of the entity.
        :type name: str
        :param type: The type of object to return.
        :type type: str
        :param start: Indicates where in the list of returned objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of objects to return. The default value is 10.
        :type count: int
        :return: A list of entities. The list is empty if there are no matching entities.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                name = "default"
                type = ObjectType.VIEW

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_entities_by_name(<parent_id>, name, type, 0, 10)
                print(entities)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entities = self.raw_api.getEntitiesByName(parent_id, name, type, start, count)
        return list(map(APIEntity.from_raw_model, entities))

    def get_entities_by_name_using_options(
        self,
        parent_id: int,
        name: str,
        type: str,
        options: dict = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> List[APIEntity]:
        """
        Get a list of entities that match the specified name and object type.
        Searching behavior can be changed by using the options parameter.

        :param parent_id: The object ID of the parent object of the entities to return.
        :type parent_id: int
        :param name: The name of the entity.
        :type name: str
        :param type: The type of object to return.
        :type type: str
        :param options: A dictionary containing the search options.

            * ignoreCase: String value.
              Set to `true` to ignore case-sensitivity while searching for entities by name.
              The default value is `false`.
        :type options: dict
        :param start: Indicates where in the list of returned objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of objects to return. The default value is 10.
        :type count: int
        :return: A list of entities that match the specified criteria.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                name = "default"
                type = ObjectType.VIEW

                # To ignore case-sensitivity while searching for entities by name
                options = {"ignoreCase": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_entities_by_name_using_options(
                        <parent_id>, name, type, options, 0, 10
                    )
                print(entities)

        .. versionadded:: 21.5.1
        """

        self._require_auth()
        if options:
            options = serialize_joined_key_value_pairs(options)
        entities = self.raw_api.getEntitiesByNameUsingOptions(
            parent_id, name, type, start, count, options
        )
        return list(map(APIEntity.from_raw_model, entities))

    def get_ip_ranged_by_ip(
        self, container_id: int, address: str, type: Optional[str] = None
    ) -> APIEntity:
        """
        Get an IPv4 or IPv6 DHCP range, block, or network containing an IPv4 or IPv6 address.

        :param container_id: The object ID of the container in which the IPv4 or IPv6 address is located.
            The entity can be a configuration, IPv4 or IPv6 block, network, or DHCP range.
        :type container_id: int
        :param address: An IPv4 or IPv6 address.
        :type address: str
        :param type: The type of object containing the IP address.
            Specify ObjectTypes.IP4Block or ObjectTypes.IP6Block, ObjectTypes.IP4Network or ObjectTypes.IP6Network,
            or ObjectTypes.DHCP4Range or ObjectTypes.DHCP6Range to find the block, network, or range containing
            the IPv4 or IPv6 address. If the type isn't specified, the method will return the most direct container for
            the IPv4 or IPv6 address.
        :type type: str
        :return: An IPv4 or IPv6 DHCP range, block, or network containing the specified IPv4 or IPv6 address.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                container_id = <configuration_id>
                address = <ip4_address>
                type = ObjectType.IP4_BLOCK

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_ip_ranged_by_ip(container_id, address, type)
                print(entity)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getIPRangedByIP(container_id, type, address))

    def get_zones_by_hint(
        self, container_id: int, options: dict, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of accessible zones of child objects for a given container_id value.

        :param container_id: The object ID of the container object.
            It can be the object ID of any object in the parent object hierarchy.
            The highest parent object is the configuration level.
        :type container_id: int
        :param options: A dictionary containing search options. It includes the following keys:

            * hint: A string specifying the start of a zone name.
            * overrideType: A string specifying the overriding of the zone. Must be a BAM Object value.
            * accessRight: A string specifying the access right for the zone. Must be a BAM Access right value.
        :type options: dict
        :param start: Indicates where in the list of objects to start returning objects.
            The list begins at an index of 0. The default value is 0.
        :type start: int
        :param count: Indicates the maximum number of child objects that this method will return.
            The maximum value is 10. The default value is 10.
        :type count: int
        :return: A list of entities
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AccessRightValues, ObjectType

                options = {
                    'hint': 'test-zone',
                    'overrideType': ObjectType.ZONE,
                    'accessRight': AccessRightValues.ViewAccess
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    zones = client.get_zones_by_hint(<container_id>, options, 0, 10)
                for zone in zones:
                    print(zone['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        zones = self.raw_api.getZonesByHint(container_id, start, count, options)
        return list(map(APIEntity.from_raw_model, zones))

    def get_host_records_by_hint(
        self, options: dict, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of objects with Host record type.

        :param options: A dictionary should contain following options:

            * hint: String value.
              If hint is not specified, searching criteria will be based on the same as zone host record.
            * retrieveFields: String value. Specify if user-defined field is returned in object's properties.
              If this option is set to 'true', user-defined field will be returned.
              If this option is set to 'false' or missing, user-defined field will not be returned.

        :type options: dict
        :param start: Indicates where in the list of objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: Indicates the maximum of child objects that this method will return.
            The value must be less than or equal to 10.
        :type count: int
        :return: A list of Host record APIEntity objects.
        :rtype: list[APIEntity]

        .. note:: The following wildcards are supported in the hint option:

            * **^** - matches the beginning of a string. For example: **^ex** matches **ex**\\ ample but not t\\ **ex**\\ t.
            * **$** - matches the end of string. For example: **ple$** matches exam\\ **ple** but not **ple**\\ ase.
            * **^ $** - matches the exact characters between the two wildcards. For example: **^example$** only matches **example**.
            * **?** - matches any one character. For example: **ex?t** matches **exit**.
            * ***** - matches zero or more characters within a string. For example: **ex*t** matches **ex**\\ i\\ **t** and **ex**\\ cellen\\ **t**.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                options = {
                    'hint': '^abc',
                    'retrieveFields': 'false'
                }
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_host_records_by_hint(options, 0, 10)
                for entity in entities:
                    print(entity['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        entities = self.raw_api.getHostRecordsByHint(start, count, options)
        return list(map(APIEntity.from_raw_model, entities))

    def add_resource_record(
        self,
        view_id: int,
        absolute_name: str,
        type: str,
        rdata: str,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a resource record. This method is a generic method for adding resource records by specifying
        the name, type, and record data arguments.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the record. If a record is added in a zone that is linked to
            an incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param type: The type of record being added.
            Valid values for this parameter are the resource record types shown in Object Types:

            * AliasRecord
            * HINFORecord
            * HostRecord
            * MXRecord
            * TXTRecord

            .. note:: To add NAPTRRecord, SRVRecord, and GenericRecord, must use addNAPTRRecord, addSRVRecord,
                and addGenericRecord methods respectively.

        :type type: str
        :param rdata: The data of the resource record in BIND format.
        :type rdata: str
        :param ttl: The time-to-live (TTL) value for the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                view_id = <view_id>
                absolute_name = "example.com"
                type = ObjectType.HOST_RECORD
                rdata = "10.0.0.10"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    resource_record_id = client.add_resource_record(view_id, absolute_name, type, rdata)
                print(resource_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addResourceRecord(view_id, absolute_name, type, rdata, ttl, properties)

    def move_resource_record(self, id: int, destination_zone: str) -> None:
        """
        Move a resource record between different zones that already exist.

        :param id: The object ID of the resource record to be moved.
        :type id: int
        :param destination_zone: The FQDN of the destination DNS zone to which the resource record
            will be moved.
        :type destination_zone: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                destination_zone = "example.com"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.move_resource_record(<id>, destination_zone)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.moveResourceRecord(id, destination_zone)

    def add_host_record(
        self,
        view_id: int,
        absolute_name: str,
        addresses: list,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a host record.

        :param view_id: The object ID of the view to which this record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the host record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param addresses: A list of IP addresses.
        :type addresses: list
        :param ttl: The time-to-live value for the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new host resource record.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                addresses = ["10.0.0.3", "10.0.0.4"]
                ttl = 3000
                properties = {"reverseRecord": "false"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    host_record_id = client.add_host_record(<view_id>, absolute_name, addresses, ttl, properties)
                print(host_record_id)

        .. versionadded:: 21.8.1
        """

        self._require_auth()
        addresses = serialize_joined_values(addresses)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addHostRecord(view_id, absolute_name, addresses, ttl, properties)

    def add_external_host_record(
        self, view_id: int, absolute_name: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add an external host record.

        :param view_id: The object ID of the view to which the external host record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the external host record. If a record is added in a zone that is linked to
            an incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new external host record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    external_host_record_id = client.add_external_host_record(<view_id>, "example.com")
                print(external_host_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addExternalHostRecord(view_id, absolute_name, properties)

    def add_bulk_host_record(
        self,
        view_id: int,
        network_id: int,
        absolute_name: str,
        start_address: str,
        number_of_addresses: int,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> List[APIEntity]:
        """
        Add a bulk of host records using auto-increment from the specific starting address.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param network_id: The object ID of The network receiving the available IP addresses.
            Each address is used for one host record.
        :type network_id: int
        :param absolute_name: The FQDN of the bulk host record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param start_address: The starting IPv4 address for getting the available addresses.
        :type start_address: str
        :param number_of_addresses: The number of addresses.
        :type number_of_addresses: int
        :param ttl: The time-to-live (TTL) value for the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including user-defined fields and excludeDHCPRange option.
            If excludeDHCPRange is true, then IP addresses within a DHCP range will be skipped.
        :type properties: dict
        :return: A list of host record APIEntity objects based on available addresses and
            number of IP addresses required. If no addresses are available, an error will be shown.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                start_address = "10.0.0.10"
                number_of_addresses = 5
                ttl = 3000

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    bulk_host_records = client.add_bulk_host_record(
                        <view_id>, <network_id>, absolute_name, start_address, number_of_addresses, ttl
                    )
                for bulk_host_record in bulk_host_records:
                    print(bulk_host_record)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        bulk_host_records = self.raw_api.addBulkHostRecord(
            view_id, absolute_name, ttl, network_id, start_address, number_of_addresses, properties
        )
        return list(map(APIEntity.from_raw_model, bulk_host_records))

    def add_generic_record(
        self,
        view_id: int,
        absolute_name: str,
        type: str,
        rdata: str,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a generic record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the generic record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param type: The type of record. Valid settings for this parameter are the generic resource record types
            supported in Address Manager: A, A6, AAAA, AFSDB, APL, CAA, CERT, DHCID, DNAME, DNSKEY, DS, ISDN, KEY,
            KX, LOC, MB, MG, MINFO, MR, NS, NSAP, PX, RP, RT, SINK, SSHFP, TLSA, WKS, TXT, and X25.
        :type type: str
        :param rdata: The data of the resource record, in BIND format.
        :type rdata: str
        :param ttl: The time-to-live (TTL) value for the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new generic resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                type = <record_type>
                rdata = <record_data>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    generic_record_id = client.add_generic_record(<view_id>, absolute_name, type, rdata)
                print(generic_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addGenericRecord(view_id, absolute_name, type, rdata, ttl, properties)

    def add_start_of_authority(
        self,
        entity_id: int,
        email: str,
        refresh: int,
        retry: int,
        expire: int,
        minimum: int,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an SOA record.

        :param entity_id: The object ID of the parent object of the SOA record.
        :type entity_id: int
        :param email: Specifies the email address of the administrator for the zones to which the SOA applies.
        :type email: str
        :param refresh: The amount of time that a secondary server waits before attempting to refresh zone files from
            the primary server. This is specified in seconds using a 32-bit integer value. RFC 1912 recommends a value
            between 1200 and 4300 seconds.
        :type refresh: int
        :param retry: Specifies the amount of time that the secondary server should wait before re-attempting
            a zone transfer from the primary server after the refresh value has expired. This is specified as a number
            of seconds using a 32-bit integer value.
        :type retry: int
        :param expire: Specifies the length of time that a secondary server will use a non-updated set of zone data
            before it stops sending queries. This is specified as a number of seconds using a 32-bit integer.
            RFC 1912 recommends a value from 1209600 to 2419200 seconds or 2 to 4 weeks.
        :type expire: int
        :param minimum: Specifies the maximum amount of time that a negative cache response is held in cache.
            A negative cache response is a response to a DNS query that does not return an IP address a failed request.
            Until this value expires, queries for this DNS record return an error.
        :type minimum: int
        :param properties: Object properties, including user-defined fields. The supported properties are:

            * ``ttl``: Time-To-Live.
            * ``mname``: Primary server.
            * ``serialNumberFormat``: Serial number format.

        :type properties: dict, optional
        :return: The object ID of the new SOA record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                email = "mail@example.com"
                refresh = 1200
                retry = 3600
                expire = 1209600
                minimum = 7200
                properties = {"ttl": 4800, "mname": "example.com"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    soa_record_id = client.add_start_of_authority(
                        <entity_id>, email, refresh, retry, expire, minimum, properties
                    )
                print(soa_record_id)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addStartOfAuthority(
            entity_id, email, refresh, retry, expire, minimum, properties
        )

    def add_alias_record(
        self,
        view_id: int,
        absolute_name: str,
        linked_record_name: str,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an alias record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the alias record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param linked_record_name: The name of the record to which the alias is being linked.
        :type linked_record_name: str
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new alias resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "alias.example.com"
                linked_record_name = "host.example.com"
                ttl = 3000

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    alias_record_id = client.add_alias_record(<view_id>, absolute_name, linked_record_name, ttl)
                print(alias_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addAliasRecord(
            view_id, absolute_name, linked_record_name, ttl, properties
        )

    def add_hinfo_record(
        self,
        view_id: int,
        absolute_name: str,
        cpu: str,
        os: str,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a HINFO record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the HINFO record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param cpu: A string providing central processing unit information.
        :type cpu: str
        :param os: A string providing operating system information.
        :type os: str
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new HINFO resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                cpu = "INTEL-386"
                os = "WIN32"
                ttl = 300

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    hinfo_record_id = client.add_hinfo_record(<view_id>, absolute_name, cpu, os, ttl)
                print(hinfo_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addHINFORecord(view_id, absolute_name, cpu, os, ttl, properties)

    def add_mx_record(
        self,
        view_id: int,
        absolute_name: str,
        linked_record_name: str,
        priority: int,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an MX record.

        :param view_id: The object ID of the view to which the MX record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the MX record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param linked_record_name: The name of the record to which the MX record is linked.
        :type linked_record_name: str
        :param priority: Specifies which mail server to send clients to first
            when multiple matching MX records are present. Multiple MX records with equal priority values are
            referred to in a round-robin fashion.
        :type priority: int
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new MX resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "mx.example.com"
                linked_record_name = "host.record.zone"
                priority = 1

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    mx_record_id = client.add_mx_record(<view_id>, absolute_name, linked_record_name, priority)
                print(mx_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addMXRecord(
            view_id, absolute_name, priority, linked_record_name, ttl, properties
        )

    def add_txt_record(
        self,
        view_id: int,
        absolute_name: str,
        data: str,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a TXT record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the text record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param data: The text data of the record.
        :type data: str
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new text record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                data = "test"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    txt_record_id = client.add_txt_record(<view_id>, absolute_name, data)
                print(txt_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTXTRecord(view_id, absolute_name, data, ttl, properties)

    def add_srv_record(
        self,
        view_id: int,
        absolute_name: str,
        linked_record_name: str,
        priority: int,
        port: int,
        weight: int,
        ttl: int = -1,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an SRV record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN of the SRV record. If a record is added in a zone that is linked to
            an incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param linked_record_name: The name of the record to which the SRV record is being linked.
        :type linked_record_name: str
        :param priority: Specifies which SRV record to use when multiple matching SRV records are present.
            The record with the lowest value takes precedence.
        :type priority: int
        :param port: The TCP/UDP port on which the service is available.
        :type port: int
        :param weight: If two matching SRV records within a zone have equal priority, the weight value is checked.
            If the weight value for one object is higher than the other,
            the record with the highest weight has its resource records returned first.
        :type weight: int
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new SRV record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "srv.example.com"
                linked_record_name = "host.example.com"
                port = <tcp_or_udp_available_port>
                priority = 10
                weight = 5

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    srv_record_id = client.add_srv_record(
                        <view_id>, absolute_name, linked_record_name, priority, port, weight
                    )
                print(srv_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addSRVRecord(
            view_id, absolute_name, priority, port, weight, linked_record_name, ttl, properties
        )

    def add_naptr_record(
        self,
        view_id: int,
        absolute_name: str,
        order: int = 0,
        preference: int = 0,
        ttl: int = -1,
        service: Optional[str] = None,
        regexp: Optional[str] = None,
        replacement: Optional[str] = None,
        flags: Optional[list] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an NAPTR record.

        :param view_id: The object ID of the view to which the record is being added.
        :type view_id: int
        :param absolute_name: The FQDN for the NAPTR record. If a record is added in a zone that is linked to an
            incremental naming policy, a single hash sign (#) must be added at the appropriate location in the FQDN.
            Depending on the policy order value, the location of the single hash sign varies.
        :type absolute_name: str
        :param order: Specifies the order in which NAPTR records are read if several are present
            and are possible matches. The lower order value takes precedence.
        :type order: int
        :param preference: Specifies the order in which NAPTR records are read if the order values are
            the same in multiple records. The lower preference value takes precedence.
        :type preference: int
        :param ttl: The time-to-live (TTL) value of the record. To ignore the TTL, set the value to -1.
        :type ttl: int
        :param service: Specifies the service used for the NAPTR record.
            Valid settings for this parameter are listed in ENUM services.
        :type service: str
        :param regexp: A regular expression, enclosed in double quotation marks, used to transform the client data.
            If a regular expression is not specified, a domain name in the replacement parameter must be specified.
        :type regexp: str
        :param replacement: Specifies a domain name as an alternative to the reg_exp.
            This parameter replaces client data with a domain name.
        :type replacement: str
        :param flags: An optional parameter used to set flag values for the record.
        :type flags: list[str]
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new NAPTR resource record.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import EnumServices

                absolute_name = "example.com"
                order = 10
                preference = 100
                ttl = 100
                service = EnumServices.SIP
                regexp = '"!^.*$!sip:jdoe@corpxyz.com!"'

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    naptr_record_id = client.add_naptr_record(
                        <view_id>, absolute_name, order, preference, ttl, service, regexp)
                print(naptr_record_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        flags = serialize_joined_values(flags)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addNAPTRRecord(
            view_id,
            absolute_name,
            order,
            preference,
            service,
            regexp,
            replacement,
            flags,
            ttl,
            properties,
        )

    def get_ip4_networks_by_hint(
        self,
        container_id: int,
        options: Optional[dict] = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> List[APIEntity]:
        """
        Get a list of IPv4 networks found under a given container object.

        :param container_id: The object ID of the container object.
            It can be the object ID of any object in the parent object hierarchy.
        :type container_id: int
        :param options: A dictionary containing search options. It includes the following keys:

            * hint: String value. This can be the prefix of the IP address or the name of a network.
            * overrideType: String value. The overrides of the zone. It must be a BAM Object value.
            * accessRight: String value. The access right for the zone. Must be a BAM Access right value.
        :type options: dict
        :param start: Indicates where in the list of objects to start returning objects.
            The list begins at an index of 0. The default value is 0.
        :type start: int
        :param count: Indicates the maximum number of child objects that this method will return.
            The maximum value is 10. The default value is 10.
        :type count: int
        :return: A list of entities
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AccessRightValues, ObjectType

                options = {
                    'hint': '172.0.0',
                    'overrideType': ObjectType.HOST_RECORD,
                    'accessRight': AccessRightValues.ViewAccess
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_networks = client.get_ip4_networks_by_hint(<container_id>, options, 0, 10)
                for zone in zones:
                    print(ip4_networks['properties'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        networks = self.raw_api.getIP4NetworksByHint(container_id, start, count, options)
        return list(map(APIEntity.from_raw_model, networks))

    def get_aliases_by_hint(
        self, options: dict, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of CNAMEs with linked record name.

        :param options: A dictionary containing the following options:

            * hint: A string value.
              If hint is not specified, searching criteria will be based on the same as zone host record.
            * retrieveFields: A string specifying if a user-defined field is returned in object's properties.
              If this option is set to 'true', the user-defined field will be returned.
              If this option is set to 'false' or missing, the user-defined field will not be returned.
        :type options: dict
        :param start: Indicates where in the list of objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: Indicates the maximum of child objects that this method will return.
            The value must be less than or equal to 10.
        :type count: int
        :return: A list of Alias APIEntity objects.
        :rtype: list[APIEntity]

        .. note:: The following wildcards are supported in the hint option:

            * **^** - matches the beginning of a string. For example: **^ex** matches **ex**\\ ample but not t\\ **ex**\\ t.
            * **$** - matches the end of string. For example: **ple$** matches exam\\ **ple** but not **ple**\\ ase.
            * **^ $** - matches the exact characters between the two wildcards. For example: **^example$** only matches **example**.
            * **?** - matches any one character. For example: **ex?t** matches **exit**.
            * ***** - matches zero or more characters within a string. For example: **ex*t** matches **ex**\\ i\\ **t** and **ex**\\ cellen\\ **t**.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                options = {
                    'hint': '^abc',
                    'retrieveFields': 'false'
                }
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_aliases_by_hint(options, 0, 10)
                for entity in entities:
                    print(entity['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        entities = self.raw_api.getAliasesByHint(start, count, options)
        return list(map(APIEntity.from_raw_model, entities))

    def get_shared_networks(self, tag_id: int) -> List[APIEntity]:
        """
        Get a list of IPv4 networks linked to the given shared network tag.

        :param tag_id: The object ID of the tag that is linked with shared IPv4 networks.
        :type tag_id: int
        :return: A list of entities of all the IPv4 networks linked to the given shared network tag
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    networks = client.get_shared_networks(<tag_id>)
                for network in networks:
                    print(network['properties'])

        .. versionadded:: 21.5.1
        """

        self._require_auth()
        networks = self.raw_api.getSharedNetworks(tag_id)
        return list(map(APIEntity.from_raw_model, networks))

    def get_network_linked_properties(self, network_id: int) -> List[APIEntity]:
        """
        Get a list of IP addresses with linked records and
        the IP addresses that are assigned as DHCP Reserved, Static, or Gateway.

        :param network_id: The object ID of the IPv4 network.
        :type network_id: int
        :return: A list of IP address APIEntity objects.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    addresses = client.get_network_linked_properties(<ip4_network_id>)
                for address in addresses:
                    print(address['properties'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        addresses = self.raw_api.getNetworkLinkedProperties(network_id)
        return list(map(APIEntity.from_raw_model, addresses))

    def link_entities(self, entity1_id: int, entity2_id: int, properties: dict = None):
        """
        Establish a link between two Address Manager entities.

        :param entity1_id: The object ID of the first entity in the pair of linked entities.
        :type entity1_id: int
        :param entity2_id: The object ID of the second entity in the pair of linked entities.
        :type entity2_id: int
        :param properties: Adds object properties, including user-defined fields.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.link_entities(<entity1_id>, <entity2_id>, <properties>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.linkEntities(entity1_id, entity2_id, properties)

    def get_linked_entities(
        self, entity_id: int, linked_type: str, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of entities linked to an entity.
        The list is empty if there are no linked entities.

        :param entity_id: The object ID of the entity to return linked entities for.
        :type entity_id: int
        :param linked_type: The type of linked entities to return.
            This value must be one of the types listed in Object types.
        :type linked_type: str
        :param start: Indicates where in the list of returned objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of objects to return. The default value is 10.
        :type count: int
        :return: A list of entities that are linked to the specified entity.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                linked_type = ObjectType.HOST_RECORD
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.get_linked_entities(<entity_id>, <linked_type>, 0, 10)
                for entity in entities:
                    print(entity['id'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        raw_data = self.raw_api.getLinkedEntities(entity_id, linked_type, start, count)
        entities = list(map(APIEntity.from_raw_model, raw_data))
        return entities

    def unlink_entities(self, entity1_id: int, entity2_id: int, properties: dict = None):
        """
        Remove the link between two Address Manager entities.

        :param entity1_id: The object ID of the first entity in the pair of linked entities.
        :type entity1_id: int
        :param entity2_id: The object ID of the second entity in the pair of linked entities.
        :type entity2_id: int
        :param properties: Adds object properties, including user-defined fields.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.unlinkEntities(<entity1_id>, <entity2_id>, <properties>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.unlinkEntities(entity1_id, entity2_id, properties)

    def get_configuration_groups(self) -> List[str]:
        """
        Get a list of all configuration groups in Address Manager.

        :return: A list of all configuration groups' names.
        :rtype: list[str]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    config_groups = client.get_configuration_groups()
                print(config_groups)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        return self.raw_api.getConfigurationGroups()

    def get_configurations_by_group(
        self, group_name: str, properties: Optional[dict] = None
    ) -> List[APIEntity]:
        """
        Get a list of configurations in Address Manager based on the name of a configuration group.

        :param group_name: The name of the configuration group in which the configurations are located.
        :type group_name: str
        :param properties: This is reserved for future use.
        :type properties: dict
        :return: A list of configurations in Address Manager based on the name of a configuration group.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                group_name = 'test_group'
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    configurations = client.get_configurations_by_group(group_name)
                for configuration in configurations:
                    print(configuration['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        properties = serialize_joined_key_value_pairs(properties)
        configurations = self.raw_api.getConfigurationsByGroup(group_name, properties)
        return list(map(APIEntity.from_raw_model, configurations))

    def get_configuration_setting(self, configuration_id: int, setting: str) -> dict:
        """
        Get a configuration setting.

        :param configuration_id: The object ID of the configuration in which the setting is to be located.
        :type configuration_id: int
        :param setting: The name of the specific setting to read.
            Only the "OPTION_INHERITANCE" setting is supported.
        :type setting: str
        :return: The configuration setting.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                setting_name = "OPTION_INHERITANCE"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    configuration_setting = client.get_configuration_setting(<configuration_id>, setting_name)
                print(configuration_setting)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return deserialize_joined_key_value_pairs(
            self.raw_api.getConfigurationSetting(configuration_id, setting)
        )

    def update_configuration_setting(self, entity_id, setting, properties):
        """
        Update a configuration setting.

        :param entity_id: The object ID of the configuration.
        :type entity_id: int
        :param setting: The name of the specific setting.
            Only the "OPTION_INHERITANCE" setting is supported.
        :type setting: str
        :param properties: The new properties of the configuration setting to be updated.
            Only the "disableDnsOptionInheritance" property is supported.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                setting = "OPTION_INHERITANCE"
                properties = {
                    "disableDnsOptionInheritance": "true"
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_configuration_setting(entity_id, setting, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.updateConfigurationSetting(entity_id, setting, properties)

    def get_all_used_locations(self) -> List[APIEntity]:
        """
        GET a list of location objects that are used to annotate other objects.

        :return: A list of location APIEntity objects.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    locations = client.get_all_used_locations()
                for location in locations:
                    print(location["name"])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        locations = self.raw_api.getAllUsedLocations()
        return list(map(APIEntity.from_raw_model, locations))

    def get_location_by_code(self, code: str) -> APIEntity:
        """
        Get the location object with a hierarchical location code.

        :param code: The hierarchical location code consists of a set of 1 to 3 alpha-numeric strings
            separated by a space. The first two characters indicate a country, followed by next three characters
            which indicate a city in UN/LOCODE. New custom locations created under a UN/LOCODE city are appended
            to the end of the hierarchy.
            For example, **CA TOR OF1** indicates:

                * **CA** - Canada
                * **TOR** - Toronto
                * **OF1** - Office 1

            .. note:: The code is case-sensitive. It must be all **UPPER CASE** letters.

                The county code and child location code should be alphanumeric strings.

        :type code: str
        :return:  The location with the specified hierarchical location code.
            If no entity is found, return None.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                code = "CA"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_location_by_code(code)
                print(entity)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getLocationByCode(code))

    def search_by_object_types(
        self, keyword: str, types: List[str], start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of entities for keywords associated with objects of specified object types.
        We can search for multiple object types with a single method call.

        :param keyword: The search keyword string.
        :type keyword: str
        :param types: The object types for which to search.
            The object type must be one of the types listed in BAM Object types.
        :type types: list[str]
        :param start: Indicates where in the list of returned objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of objects to return. The default value is 10.
        :type count: int
        :return: A list of entities matching the keyword text and the category type, or an empty list.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                keyword = 'test'
                types = ['Configuration', 'View']
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.search_by_object_types(keyword, types, 0, 10)
                for entity in entities:
                    print(entity['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        types = ",".join(types)
        entities = self.raw_api.searchByObjectTypes(keyword, types, start, count)
        return list(map(APIEntity.from_raw_model, entities))

    def search_by_category(
        self, category: str, keyword: str, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIEntity]:
        """
        Get a list of entities by searching for keywords associated with objects of a specified object category.

        :param category: The entity category to search.
            This must be one of the entity categories listed in BAM Entity categories.
        :type category: str
        :param keyword: The search keyword string. The following wildcards are supported in the options:

            * **^** - matches the beginning of a string. For example: **^ex** matches **ex**\\ ample but not t\\ **ex**\\ t.
            * **$** - matches the end of string. For example: **ple$** matches exam\\ **ple** but not **ple**\\ ase.
            * **^ $** - matches the exact characters between the two wildcards. For example: **^example$** only matches **example**.
            * **?** - matches any one character. For example: **ex?t** matches **exit**.
            * ***** - matches zero or more characters within a string. For example: **ex*t** matches **ex**\\ i\\ **t** and **ex**\\ cellen\\ **t**.

        :type keyword: str
        :param start: Indicates where in the list of returned objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of objects to return. The default value is 10.
        :type count: int
        :return: A list of entities matching the keyword text and the category type, or an empty list.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                keyword = 'test'
                category = 'CONFIGURATION'
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.search_by_category(category, keyword, 0, 10)
                for entity in entities:
                    print(entity['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        entities = self.raw_api.searchByCategory(keyword, category, start, count)
        return list(map(APIEntity.from_raw_model, entities))

    def custom_search(
        self,
        type: str,
        filters: dict,
        options: Optional[list] = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> List[APIEntity]:
        """
        Search for a list of entities by specifying object properties.

        :param type: The object type aiming to search. This must be one for the following object types:

            * IP4Block
            * IP4Network
            * IP4Addr
            * GenericRecord
            * HostRecord
            * Any other objects with user-defined fields.
        :type type: str
        :param filters: The list of valid supported search field names.
        :type filters: dict
        :param options: The list of search options specifying the search behavior. Reserved for future use.
        :type options: list
        :param start: Indicates where in the list of returned objects to start returning objects.
            The value must be a positive value, and the default value is 0.
        :type start: int
        :param count: The maximum number of objects to return. The value must be a positive value between 1 and 1000.
            The default value is 10.
        :type count: int
        :return: A list of APIEntities matching the specified object properties or an empty list.
            The APIEntities will at least contain Object Type, Object ID, Object Name, and Object Properties.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                type = ObjectType.IP4_NETWORK
                filters = {'inheritDNSRestrictions': 'true'}
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entities = client.custom_search(type, filters)
                for entity in entities:
                    print(entity['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        filters = serialize_joined_key_value_pairs(filters).split("|")
        filters = list(filter(None, filters))
        entities = self.raw_api.customSearch(filters, type, options, start, count)
        return list(map(APIEntity.from_raw_model, entities))

    def add_view(self, configuration_id: int, name: str, properties: Optional[dict] = None) -> int:
        """
        Add a DNS view.

        :param configuration_id: The object ID of the configuration in which the new DNS view is being located.
        :type configuration_id: int
        :param name: The name of the view.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new DNS view.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {<UDF_name>: <value>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    view_id = client.add_view(<configuration_id>, "view-name", properties)
                print(view_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addView(configuration_id, name, properties)

    def add_acl(self, entity_id: int, name: str, properties: list[str]) -> int:
        """
        Add an Access Control List (ACL).

        :param entity_id: The object ID of the configuration in which an ACL need to be added.
        :type entity_id: int
        :param name: The name of the ACL.
        :type name: str
        :param properties: List of options. Use an exclamation mark to exclude a certain option.
        :type properties: list[str]
        :return: The object ID of the newly created ACL.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                name = "ACl_name"
                properties = ["127.0.0.13", "!127.0.0.14"]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    acl_id = client.add_acl(entity_id, name, properties)
                print(acl_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = "aclValues=" + serialize_joined_values(properties)
        return self.raw_api.addACL(entity_id, name, properties)

    def add_zone(
        self, entity_id: int, absolute_name: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DNS zone.

        :param entity_id: The object ID of the parent object to which the zone is being added.
            For top-level domains, the parent object is a DNS view.
            For sub-zones, the parent object is a top-level domain or DNS zone.
        :type entity_id: int
        :param absolute_name: The FQDN of the zone with no trailing dot.
        :type absolute_name: str
        :param properties: Object properties,
            including a flag for deployment, an optional network template association, and user-defined fields.
        :type properties: dict
        :return: The object ID of the new DNS zone.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                absolute_name = "example.com"
                properties = {
                    "deployable": "true",
                    "template": <zone_template_id>,
                    <UDF_name>: <UDF_value>,
                }

                 with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    zone_id = client.add_zone(<entity_id>, absolute_name, properties)
                print(zone_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addZone(entity_id, absolute_name, properties)

    def add_device(
        self,
        configuration_id: int,
        device_name: str,
        device_type_id: int = 0,
        device_subtype_id: int = 0,
        ip4_addresses: Optional[list] = None,
        ip6_addresses: Optional[list] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a device to a configuration.

        :param configuration_id: The object ID of the configuration in which the device is to be located.
        :type configuration_id: int
        :param device_name: The name of the device.
        :type device_name: str
        :param device_type_id: The object ID of the device type with which the device is associated.
            The value can be 0 if you do not wish to associate a device type to the device.
        :type device_type_id: int
        :param device_subtype_id: The object ID of the device sub-type with which the device is associated.
            The value can be 0 if you do not wish to associate a device sub-type to the device.
        :type device_subtype_id: int
        :param ip4_addresses: One or more IPv4 addresses to which the device is assigned.
        :type ip4_addresses: list[str]
        :param ip6_addresses: One or more IPv6 addresses to which the device is assigned.
        :type ip6_addresses: list[str]
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new device.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                configuration_id = <configuration_id>
                device_name = "device_name"
                device_type_id = <device_type_id>
                device_subtype_id = <device_subtype_id>
                ip4_addresses = ["127.0.0.13", "127.0.0.26"]
                ip6_addresses = ["2001:DB8::1322:33FF:FE44:5566"]
                properties = {<UDF_name>: <UDF_value>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    device_id = client.add_device(
                        configuration_id,
                        device_name,
                        device_type_id,
                        device_subtype_id,
                        ip4_addresses,
                        ip6_addresses,
                        properties
                    )
                print(device_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        ip4_addresses = serialize_joined_values(ip4_addresses)
        ip6_addresses = serialize_joined_values(ip6_addresses)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDevice(
            configuration_id,
            device_name,
            device_type_id,
            device_subtype_id,
            ip4_addresses,
            ip6_addresses,
            properties,
        )

    def add_device_type(self, name: str, properties: Optional[dict] = None) -> int:
        """
        Add a device type to Address Manager.

        :param name: The descriptive name for the device type.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new device type.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {<UDF_name>: <UDF_value>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    device_type_id = client.add_device_type("device_type_name", properties)
                print(device_type_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDeviceType(name, properties)

    def add_device_subtype(
        self, device_type_id: int, name: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a device sub-type to Address Manager.

        :param device_type_id: The object ID of the parent device type.
        :type device_type_id: int
        :param name: The descriptive name for the device sub-type.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new device sub-type.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                device_type_id = <device_type_id>
                name = "device_subtype_name"
                properties = {<UDF_name>: <UDF_value>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    device_subtype_id = client.add_device_subtype(device_type_id, name, properties)
                print(device_subtype_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDeviceSubtype(device_type_id, name, properties)

    # endregion Entity

    # region Object Tags

    def add_tag_group(self, name: str, properties: Optional[dict] = None) -> int:
        """
        Add an object tag group.

        :param name: The name of the tag group.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new tag group.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tag_group_id = client.add_tag_group("tag-group-name")
                print(tag_group_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTagGroup(name, properties)

    def add_tag(self, entity_id: int, name: str, properties: Optional[dict] = None) -> int:
        """
        Add an object tag.

        :param entity_id: The object ID of the parent for this object tag.
            The parent is either an object tag or an object tag group.
        :type entity_id: int
        :param name: The name of the object tag.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new object tag.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tag_id = client.add_tag(<entity_id>, "tag-name")
                print(tag_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTag(entity_id, name, properties)

    # endregion Object Tags

    # region ENUM

    def add_enum_zone(self, entity_id: int, prefix: int, properties: Optional[dict] = None) -> int:
        """
        Add an ENUM zone.

        :param entity_id: The object ID of the parent object of the ENUM zone.
        :type entity_id: int
        :param prefix: The number prefix for the ENUM zone.
        :type prefix: int
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new ENUM zone.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    enum_zone_id = client.add_enum_zone(<entity_id>, 100)
                print(enum_zone_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addEnumZone(entity_id, prefix, properties)

    def add_enum_number(self, enum_zone_id: int, number: int, properties: dict) -> int:
        """
        Add an ENUM number.

        :param enum_zone_id: The object ID of an ENUM zone.
        :type enum_zone_id: int
        :param number: The ENUM number.
        :type number: int
        :param properties: Object properties and user-defined fields. The dictionary should contain
            the following key:

            * **data** - The value is a comma-separated list of values for **service**,
                **URI**, **comment**, and **ttl**.

        :type properties: dict
        :return: The object ID of the new ENUM number.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                number = 100
                properties = {"data": "H323,example,a comment,300"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    enum_number_id = client.add_enum_number(<enum_zone_id>, number, properties)
                print(enum_number_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addEnumNumber(enum_zone_id, number, properties)

    # endregion ENUM

    # region DNS Zone Templates

    def add_zone_template(
        self, entity_id: int, name: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DNS zone template.

        :param entity_id: The object ID of the DNS view if adding a view-level zone template.
            The object ID of the configuration if adding a configuration-level zone template.
        :type entity_id: int
        :param name: The name of the DNS zone template.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new DNS zone template.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <view_id>
                name = <zone_template_name>
                properties = {<UDF_name>: <UDF_value>}

                 with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    zone_template_id = client.add_zone_template(entity_id, name, properties)
                print(zone_template_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addZoneTemplate(entity_id, name, properties)

    def assign_or_update_template(self, zone_id: int, template_id: int, properties: dict):
        """
        Assign, update, or remove a DNS zone template.

        :param zone_id: The object ID of the zone to which the zone template is being assigned or updated.
        :type zone_id: int
        :param template_id: The object ID of the DNS zone template. To remove a template, set this value to 0 zero.
        :type template_id: int
        :param properties: A dictionary containing the following settings:

            * templateType - Mandatory. Specify the type of template on which this operation is being performed.
              The only possible value is "ZoneTemplate".
            * zoneTemplateReapplyMode - Optional. Specify the re-apply mode for various properties of the template.
              If the re-apply mode is not specified, the default value is templateReapplyModeIgnore.
              The possible values are: ZoneTemplateReapplyMode.OVERWRITE, ZoneTemplateReapplyMode.UPDATE,
              ZoneTemplateReapplyMode.IGNORE

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                properties = {"templateType": ObjectType.ZONE_TEMPLATE}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.assign_or_update_template(<zone_id>, <template_id>, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.assignOrUpdateTemplate(zone_id, template_id, properties)

    def reapply_template(self, id: int, properties: dict):
        """
        Reapply a DNS zone template.

        :param id: The object ID of the DNS zone template being assigned or updated.
        :type id: int
        :param properties: A dictionary containing the following settings:

            * templateType - Mandatory. Specify the type of template on which this operation is being performed.
              The only possible value is "ZoneTemplate".
            * zoneTemplateReapplyMode - Optional. Specify the re-apply mode for various properties of the template.
              If the re-apply mode is not specified, the default value is templateReapplyModeIgnore.
              The possible values are: ZoneTemplateReapplyMode.OVERWRITE, ZoneTemplateReapplyMode.UPDATE,
              ZoneTemplateReapplyMode.IGNORE

            .. note::

                * ZoneTemplateReapplyMode.OVERWRITE is NOT applicable for Gateway and Reserved Addresses.
                  Use ZoneTemplateReapplyMode.UPDATE instead to update.
                * ZoneTemplateReapplyMode.UPDATE is NOT applicable for
                  Reserved DHCP Ranges, IP Groups and Zone Templates.
                  Use ZoneTemplateReapplyMode.OVERWRITE instead to update.
                * Both ZoneTemplateReapplyMode.UPDATE and ZoneTemplateReapplyMode.OVERWRITE
                  are applicable for Deployment Options.

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType, ZoneTemplateReapplyMode

                properties = {
                    "templateType": ObjectType.ZONE_TEMPLATE,
                    "zoneTemplateReapplyMode": ZoneTemplateReapplyMode.OVERWRITE,
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.reapply_template(<template_id>, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.reapplyTemplate(id, properties)

    # endregion DNS Zone Templates

    # region DNSSEC Signing Policies

    def get_ksk(self, entity_id: int, key_format: str) -> List[str]:
        """
        Get a list of strings containing all active Key Signing Keys (KSK) for an entity.

        :param entity_id: The object ID of the entity associated with the KSK.
            The only supported entity types are zone, IPv4 block, and IPv4 network.
        :type entity_id: int
        :param key_format: The output format of the KSK.
            The value must be one of the constants listed in BAM's DNSSEC key format:

                * DNS_KEY
                * DS_RECORD
                * TRUST_ANCHOR

        :type key_format: str
        :return: A list of strings containing up to two active KSK(s) for an entity.
        :rtype: list[str]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                key_format = "DNS_KEY"
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    key_list = client.get_ksk(<zone_id>, key_format)
                for key in key_list:
                    print(key)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        return self.raw_api.getKSK(entity_id, key_format)

    # endregion DNSSEC Signing Policies

    # region Access Rights

    def add_access_right(
        self,
        entity_id: int,
        user_id: int,
        value: str,
        overrides: Optional[dict] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an access right to an object.

        :param entity_id: The object ID of the entity to which the access right is being added.
            Set to zero (0) if you are adding the access right to the root level default access rights.
        :type entity_id: int
        :param user_id: The object ID of the user to whom this access right applies.
        :type user_id: int
        :param value: The value of the access right being added. This value must be one of the following items:

            * ADD
            * CHANGE
            * FULL
            * HIDE
            * VIEW

        :type value: str
        :param overrides: A dictionary of type-specific overrides.
        :type overrides: dict
        :param properties: A dictionary including the following options:

            * **workflowLevel** - valid values for this option are:

                * NONE - changes made by the user or group take effect immediately.
                * RECOMMEND - changes made by the user or group are saved as change requests
                  and must be reviewed and approved before they take effect.
                * APPROVE - changes made by the user or group take effect immediately
                  and the user or group can approve change requests from other users or groups.

            * **deploymentAllowed** - either true or false, to indicate whether or not the user
              or group can perform a full deployment of data from the configuration to a managed server.
            * **quickDeploymentAllowed** - either true or false, to indicate whether or not the user
              or group can instantly deploy changed DNS resource records.

            .. note::

                * All of these properties are optional.
                * The deploymentAllowed property is applicable only for configuration, server,
                  or root with Full access rights.
                * The workflowLevel property is applicable only for Change, Add, or Full access rights.

        :type properties: dict
        :return: The object ID of the new access right.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AccessRightValues

                entity_id = 0
                user_id = <user_id>
                value = AccessRightValues.FullAccess
                overrides = {"AliasRecord": "ADD", "Configuration": "VIEW"}
                properties = {"deploymentAllowed": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    access_right_id = client.add_access_right(entity_id, user_id, value, overrides, properties)
                print(access_right_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        overrides = serialize_joined_key_value_pairs(overrides)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addAccessRight(entity_id, user_id, value, overrides, properties)

    def get_access_right(self, entity_id: int, user_id: int) -> APIAccessRight:
        """
        Get the access right to an object.

        :param entity_id: The object ID of the entity to which the access right is assigned.
        :type entity_id: int
        :param user_id: The object ID of the user to whom the access right is applied.
        :type user_id: int
        :return: The access right for the specified object.
        :rtype: APIAccessRight

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <view_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    access_right = client.get_access_right(entity_id, <user_id>)
                print(access_right)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        access_right = self.raw_api.getAccessRight(entity_id, user_id)
        return APIAccessRight.from_raw_model(access_right)

    def update_access_right(
        self,
        entity_id: int,
        user_id: int,
        value: str,
        overrides: Optional[dict] = None,
        properties: Optional[dict] = None,
    ):
        """
        Update the access right for an object.

        :param entity_id: The object ID of the entity to which the access right is assigned.
            Set to zero (0) if you are adding the access right to the root level default access rights.
        :type entity_id: int
        :param user_id: The object ID of the user to whom the access right is assigned. This value is not mutable.
        :type user_id: int
        :param value: The value of the access right being added. This value must be one of the following items:

            * ADD
            * CHANGE
            * FULL
            * HIDE
            * VIEW

        :type value: str
        :param overrides: A dictionary of type-specific overrides.
        :type overrides: dict
        :param properties: A dictionary including the following options:

            * **workflowLevel** - valid values for this option are:

                * NONE - changes made by the user or group take effect immediately.
                * RECOMMEND - changes made by the user or group are saved as change requests
                  and must be reviewed and approved before they take effect.
                * APPROVE - changes made by the user or group take effect immediately
                  and the user or group can approve change requests from other users or groups.

            * **deploymentAllowed** - either true or false, to indicate whether or not the user
              or group can perform a full deployment of data from the configuration to a managed server.
            * **quickDeploymentAllowed** - either true or false, to indicate whether or not the user
              or group can instantly deploy changed DNS resource records.

            .. note::

                * All of these properties are optional.
                * The deploymentAllowed property is applicable only for configuration, server,
                  or root with Full access rights.
                * The workflowLevel property is applicable only for Change, Add, or Full access rights.

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AccessRightValues
                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = 0
                user_id = <user_id>
                value = AccessRightValues.FullAccess
                overrides = {'IP4Block': 'FULL', 'View': 'FULL'}
                properties = {
                    "deploymentAllowed": "true",
                    "quickDeploymentAllowed": "true",
                    "workflowLevel": "RECOMMEND",
                }
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_access_right(entity_id, user_id, value, overrides, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        overrides = serialize_joined_key_value_pairs(overrides)
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.updateAccessRight(entity_id, user_id, value, overrides, properties)

    def delete_access_right(self, entity_id: int, user_id: int):
        """
        Delete the access right of an object.

        :param entity_id: The object ID of the entity to which the access right is assigned.
        :type entity_id: int
        :param user_id: The object ID of the user to whom this access right is applied.
        :type user_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <view_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_access_right(entity_id, <user_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteAccessRight(entity_id, user_id)

    def get_access_rights_for_entity(
        self, id: int, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIAccessRight]:
        """
        Get a list of access rights of an entity.

        :param id: The object ID of the entity whose access rights are returned.
        :type id: int
        :param start: Indicates where in the list of child access right objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of access right child objects to return. The default value is 10.
        :type count: int
        :return: A list of access rights of an entity.
        :rtype: list[APIAccessRight]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    access_rights = client.get_access_rights_for_entity(<id>, 0, 10)
                for access_right in access_rights:
                    print(access_right)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        access_rights = self.raw_api.getAccessRightsForEntity(id, start, count)
        return list(map(APIAccessRight.from_raw_model, access_rights))

    def get_access_rights_for_user(
        self, id: int, start: int = 0, count: int = DEFAULT_COUNT
    ) -> List[APIAccessRight]:
        """
        Get a list of access rights for a user.

        :param id: The object ID of the user whose access rights are returned.
        :type id: int
        :param start: Indicates where in the list of child access right objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: The maximum number of access right child objects to return. The default value is 10.
        :type count: int
        :return: A list of access rights for the specified user.
        :rtype: list[APIAccessRight]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    access_rights = client.get_access_rights_for_user(<id>, 0, 10)
                for access_right in access_rights:
                    print(access_right)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        access_rights = self.raw_api.getAccessRightsForUser(id, start, count)
        return list(map(APIAccessRight.from_raw_model, access_rights))

    # endregion AccessRight

    # region Response Policy

    def find_response_policies_with_item(
        self, configuration_id: int, item_name: str, options: Optional[dict] = None
    ) -> List[APIEntity]:
        """
        Find local DNS response policies with their associated response policy items.

        :param configuration_id: The object ID of the configuration to which the local response policies are located.
            To find local response policies from all configurations, set the value of this parameter to 0
        :type configuration_id: int
        :param item_name: The fully qualified domain name (FQDN) of the response policy item.
            The exact FQDN of the response policy item must be used.
        :type item_name: str
        :param options: Reserved for future use.
        :type options: dict
        :return: A list of local response policies.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                item_name = 'item'
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    policies = client.find_response_policies_with_item(<configuration_id>, item_name)
                for policy in policies:
                    print(policy['name'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        policies = self.raw_api.findResponsePoliciesWithItem(configuration_id, item_name, options)
        return list(map(APIEntity.from_raw_model, policies))

    # endregion Response Policy

    # region Deployment Roles

    def add_dns_deployment_role(
        self, entity_id: int, server_interface_id: int, type: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DNS deployment role to an object.

        :param entity_id: The object ID of the entity to which the deployment role is added.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the role is added.
        :type server_interface_id: int
        :param type: The type of DNS role is to be added.
            The type must be one of those listed in DNS deployment role type.
        :type type: str
        :param properties: Object properties,
            including the View associated with this DNS deployment role and user-defined fields.
        :type properties: dict
        :return: The ID of the added DNS deployment role object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DNSDeploymentRoleType

                entity_id = <entity_id>
                server_interface_id = <server_interface_id>
                type = DNSDeploymentRoleType.MASTER
                properties = {"view": <view_id>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dns_deployment_role_id = client.add_dns_deployment_role(
                        entity_id, server_interface_id, type, properties
                    )
                print(dns_deployment_role_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDNSDeploymentRole(entity_id, server_interface_id, type, properties)

    def get_dns_deployment_role(
        self, entity_id: int, server_interface_id: int
    ) -> APIDeploymentRole:
        """
        Get the DNS deployment role of an object.

        :param entity_id: The object ID of the object to which the DNS deployment role is assigned.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the DNS deployment role is assigned.
        :type server_interface_id: int
        :return: The DNS deployment role of the specified object, or None if no role is defined.
        :rtype: APIDeploymentRole

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dns_deployment_role = client.get_dns_deployment_role(<view_id>, <server_interface_id>)
                print(dns_deployment_role)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        dns_deployment_role = self.raw_api.getDNSDeploymentRole(entity_id, server_interface_id)
        return APIDeploymentRole.from_raw_model(dns_deployment_role)

    def update_dns_deployment_role(self, role: APIDeploymentRole):
        """
        Update a DNS deployment role.

        :param role: The DNS deployment role object to update.
        :type role: APIDeploymentRole

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DNSDeploymentRoleType
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentRole

                role = APIDeploymentRole(
                    id=<deployment_role_id>,
                    entityId=<zone_id>,
                    serverInterfaceId=<server_interface_id>,
                    type=DNSDeploymentRoleType.MASTER,
                    service="DNS",
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dns_deployment_role(role)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDNSDeploymentRole(APIDeploymentRole.to_raw_model(role))

    def delete_dns_deployment_role(self, entity_id: int, server_interface_id: int):
        """
        Delete a DNS deployment role.

        :param entity_id: The object ID of the object from which the DNS deployment role is being deleted.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the DNS deployment role is assigned.
        :type server_interface_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <view_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dns_deployment_role(entity_id, <server_interface_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDNSDeploymentRole(entity_id, server_interface_id)

    def get_dns_deployment_role_for_view(
        self, view_id: int, entity_id: int, server_interface_id: int
    ) -> APIDeploymentRole:
        """
        Get the DNS deployment role assigned to a view-level objects in the IP space for ARPA zones.

        :param view_id: The object ID of the view in which the DNS deployment role is assigned.
        :type view_id: int
        :param entity_id: The object ID of the object to which the DNS deployment role is assigned.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the DNS deployment role is assigned.
        :type server_interface_id: int
        :return: The requested APIDeploymentRole object.
        :rtype: APIDeploymentRole

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <ip4_network_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dns_deployment_role = client.get_dns_deployment_role_for_view(
                        <view_id>, entity_id, <server_interface_id>
                    )
                print(dns_deployment_role.get('service'))

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        dns_deployment_role = self.raw_api.getDNSDeploymentRoleForView(
            entity_id, server_interface_id, view_id
        )
        return APIDeploymentRole.from_raw_model(dns_deployment_role)

    def delete_dns_deployment_role_for_view(
        self, view_id: int, entity_id: int, server_interface_id: int
    ):
        """
        Delete the DNS deployment role assigned to view-level object in the IP space for ARPA zones.

        :param view_id: The object ID of the view from which the DNS deployment role is being deleted.
        :type view_id: int
        :param entity_id: The object ID of the entity from which the DNS deployment role is being deleted.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the DNS deployment role is assigned.
        :type server_interface_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dns_deployment_role_for_view(<view_id>, <entity_id>, <server_interface_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDNSDeploymentRoleForView(entity_id, server_interface_id, view_id)

    def get_deployment_roles(self, entity_id: int) -> List[APIDeploymentRole]:
        """
        Get the DNS and DHCP deployment roles associated with an object.
        For DNS views and zones, the result contains DNS deployment roles.
        For IP address space objects, such as IPv4 blocks and networks, IPv6 blocks and networks, DHCP classes,
        and MAC pools, the result contains DNS and DHCP deployment roles.

        :param entity_id: The object ID of a DNS view, DNS zone, IPv4 block or network, IPv6 block or network,
            DHCP class, or MAC pool.
        :type entity_id: int
        :return: A list of the DNS and DHCP deployment roles associated with the specified object.
        :rtype: list[APIDeploymentRole].

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_roles = client.get_deployment_roles(<entity_id>)
                for deployment_role in deployment_roles:
                    print(deployment_role.get('type'))

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        deployment_roles = self.raw_api.getDeploymentRoles(entity_id)
        return list(map(APIDeploymentRole.from_raw_model, deployment_roles))

    def get_server_deployment_roles(self, server_id: int) -> List[APIDeploymentRole]:
        """
        Get a list of all deployment roles associated with a server.

        :param server_id:  The object ID of the server with which deployment roles are associated.
        :type server_id: int
        :return: A list of all deployment roles associated with the server.
        :rtype: list[APIDeploymentRole]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_roles = client.get_server_deployment_roles(<server_id>)
                for deployment_role in deployment_roles:
                    print(deployment_role)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        deployment_roles = self.raw_api.getServerDeploymentRoles(server_id)
        return list(map(APIDeploymentRole.from_raw_model, deployment_roles))

    def get_server_for_role(self, id: int) -> APIEntity:
        """
        Get the server associated with a deployment role.

        :param id: The object ID of the deployment role whose server is to be returned.
        :type id: int
        :return: APIEntity object representing the server associated with the specified deployment role.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    server = client.get_server_for_role(<id>)
                print(server)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        server = self.raw_api.getServerForRole(id)
        return APIEntity.from_raw_model(server)

    def add_dhcp_deployment_role(
        self, entity_id: int, server_interface_id: int, type: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DHCP deployment role to an object.

        :param entity_id: The object ID of the object to which the deployment role is being added.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the role is being added.
        :type server_interface_id: int
        :param type: The type of DHCP role to add. The type must be one of the DHCPDeploymentRoleType constant.
        :type type: str
        :param properties: A dictionary containing options including:

            * **inherited** - either true or false, indicates whether or not the deployment role was inherited.
            * **secondaryServerInterfaceId** - the object ID of the secondary server interface for a DHCP failover.
        :type properties: dict
        :return: The object ID of the new DHCP server role object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPDeploymentRoleType

                type = DHCPDeploymentRoleType.MASTER
                properties = {"secondaryServerInterfaceId": <secondary_server_interface_id>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_role_id = client.add_dhcp_deployment_role(
                        <ip4_network_id>, <server_interface_id>, type, properties
                    )
                print(deployment_role_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPDeploymentRole(entity_id, server_interface_id, type, properties)

    def get_dhcp_deployment_role(
        self, entity_id: int, server_interface_id: int
    ) -> APIDeploymentRole:
        """
        Get the DHCP deployment role assigned to an object.

        :param entity_id: The object ID of the object to which the deployment role is assigned.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface to which the role is assigned.
        :type server_interface_id: int
        :return: The DHCP deployment role assigned to the specified object,
            or an empty APIDeploymentRole if no role is defined.
        :rtype: APIDeploymentRole

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_role = client.get_dhcp_deployment_role(<entity_id>, <server_interface_id>)
                print(deployment_role)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        deployment_role = self.raw_api.getDHCPDeploymentRole(entity_id, server_interface_id)
        return APIDeploymentRole.from_raw_model(deployment_role)

    def update_dhcp_deployment_role(self, role: APIDeploymentRole):
        """
        Update a DHCP deployment role.

        :param role: The DHCP deployment role object to update.
        :type role: APIDeploymentRole

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentRole
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPDeploymentRoleType

                role = APIDeploymentRole(
                    id=<dhcp4_role_id>,
                    entityId=<ip4_network_id>,
                    serverInterfaceId=<server_interface_id>,
                    type=DHCPDeploymentRoleType.MASTER,
                    service="DHCP",
                    properties={"secondaryServerInterfaceId": <secondary_server_interface_id>}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp_deployment_role(role)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDHCPDeploymentRole(APIDeploymentRole.to_raw_model(role))

    def delete_dhcp_deployment_role(self, entity_id: int, server_interface_id: int):
        """
        Delete a DHCP deployment role.

        :param entity_id: The object ID of the object from which the deployment role is to be deleted.
        :type entity_id: int
        :param server_interface_id: The object ID of the server interface from which the deployment roles
            is to be deleted.
        :type server_interface_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <view_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp_deployment_role(entity_id, <server_interface_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCPDeploymentRole(entity_id, server_interface_id)

    def move_deployment_roles(
        self,
        source_server_id: int,
        target_server_interface_id: int,
        move_dns_roles: bool,
        move_dhcp_roles: bool,
        options: Optional[dict] = None,
    ) -> None:
        """
        Move DNS/DHCP deployment roles from a server to the specified interface of another server.

        :param source_server_id: The object ID of the server that contains the roles.
        :type source_server_id: int
        :param target_server_interface_id: The object ID of the server interface of the server to
            which the roles are to be moved.
        :type target_server_interface_id: int
        :param move_dns_roles: If set to ``True``, all DNS roles will be moved to the target server
            interface.
        :type move_dns_roles: bool
        :param move_dhcp_roles: If set to ``True``, all DHCP roles will be moved to the target
            server interface.
        :type move_dhcp_roles: bool
        :param options: This is reserved for future use.
        :type options: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.move_deployment_roles(
                        <source_server_id>, <target_server_interface_id>, True, False
                    )

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        self.raw_api.moveDeploymentRoles(
            source_server_id, target_server_interface_id, move_dns_roles, move_dhcp_roles, options
        )

    # endregion Deployment Roles

    # region Deployment Options

    def add_raw_deployment_option(
        self, entity_id: int, type: str, value: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a raw deployment option. Raw deployment options are added to DNS or DHCP services in a format
        that will be passed to the service when deployed.

        :param entity_id: The object ID of the entity to which the deployment option is being added.
        :type entity_id: int
        :param type: The type of option. The type must be one of the following values:

            * DNS_RAW
            * DHCP_RAW
            * DHCPV6_RAW

        :type type: str
        :param value: The raw option value. The maximum supported characters are 65,536.
            The raw option will be passed to the DNS or DHCP service on the managed server exactly as you enter here.
        :type value: str
        :param properties: Object properties, including associated server and server group, and user-defined fields.
        :type properties: dict
        :return: The object ID of the newly added Raw option.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                type = ObjectType.DNS_RAW_OPTION
                value = "Example"
                properties = {"server": <server_id>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_id = client.add_raw_deployment_option(<ip4_network_id>, type, value, properties)
                print(deployment_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        properties = serialize_joined_key_value_pairs(properties)
        deployment_properties = {"type": type, "value": value, "properties": properties}
        return self.raw_api.addRawDeploymentOption(entity_id, deployment_properties)

    def add_dns_deployment_option(
        self,
        entity_id: int,
        option_name: str,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DNS deployment option.

        :param entity_id: The object ID of the entity to which the DNS deployment option is being
            added.
        :type entity_id: int
        :param option_name: The name of the DNS option being added.
            This name must be one of the constants listed listed in DNS options.
        :type option_name: str
        :param value: The list of raw option values.
            The list is processed before it is sent to Address Manager.
            The total length of the result (all values and a separator between each of
            them) should not exceed 65,536 characters.
            Depending on the type of deployment option added, the format of the values might differ.

            .. note:: If adding a Reverse Zone Name Format, the following values are supported:

                * ReverseZoneFormatType.STARTIP_NETMASK_NET or "[start-ip]-[net-mask].[net].inaddr.arpa"
                * ReverseZoneFormatType.STARTIP_ENDIP_NET or "[start-ip]-[end-ip].[net].in-addr.arpa"
                * ReverseZoneFormatType.STARTIP_SLASH_NETMASK_NET or "[start-ip]/[netmask].[net].in-addr.arpa"
                * ReverseZoneFormatType.STARTIP_SLASH_ENDIP_NET or "[start-ip]/[end-ip].[net].inaddr.arpa"
                * ReverseZoneFormatType.CUSTOM + ReverseZoneFormatType.SEPARATOR + "[customformat-value]"
                  or “custom:<custom-format-value>”

        :type value: list[str]
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The ID of the added DNS deployment option.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <zone_id>
                option_name = 'update-policy'
                value = [
                    ["grant", "test", "subdomain", "sub.domain.com", "ANY"],
                    ["deny", "test2", "self", "test2", "ANY"],
                ]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_option_id = client.add_dns_deployment_option(entity_id, option_name, value)
                print(deployment_option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDNSDeploymentOption(entity_id, option_name, value, properties)

    def get_dns_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ) -> APIDeploymentOption:
        """
        Get the DNS deployment option assigned to an object, excluding the options inherited from
        the higher-level parent objects.

        :param entity_id: The object ID of the entity to which this deployment option is assigned.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which this option is assigned.
            To retrieve an option that has not been assigned to a server role, set this value to 0 (zero).
        :type server_id: int
        :param option_name: The name of the DNS option.
            This name must be one of the constants listed for DNS options.
        :type option_name: str
        :return: An instance of the type APIDeploymentOption
            that represents the DNS deployment option or empty if none were found.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <entity_id>
                server_id = <server_id>
                option_name = "update-policy"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dns_deployment_option = client.get_dns_deployment_option(entity_id, server_id, option_name)
                print(dns_deployment_option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIDeploymentOption.from_raw_model(
            self.raw_api.getDNSDeploymentOption(entity_id, option_name, server_id)
        )

    def update_dns_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DNS option.

        :param option: The DNS option to update.

            .. note:: Depending on the type of deployment option, the format of the value might differ.

        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption

                option = APIDeploymentOption(
                    id=<entity_id>,
                    name="allow-notify",
                    value=["10.0.0.6"],
                    properties={<udf_name>: <udf_value>}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dns_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        body = APIDeploymentOption.to_raw_model(option)
        self.raw_api.updateDNSDeploymentOption(body)

    def delete_dns_deployment_option(self, entity_id: int, server_id: int, option_name: str):
        """
        Delete a DNS option.

        :param entity_id: The object ID of the entity to which the deployment option is assigned.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which the option is assigned.
            To delete an option that has not been assigned to a server role, set this value to 0 (zero).
        :type server_id: int
        :param option_name: The name of the DNS option being deleted.
            This name must be one of the constants listed in DNS options.
        :type option_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <zone_id>
                option_name = 'update-policy'

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dns_deployment_option(entity_id, <server_id>, option_name)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDNSDeploymentOption(entity_id, option_name, server_id)

    def update_raw_deployment_option(self, option: APIDeploymentOption):
        """
        Update a raw deployment option.

        :param option: The raw deployment option to update.
        :type option: APIDeploymentOption

        .. note:: The type of the option must be one of the following values:

            * DNS_RAW
            * DHCP_RAW
            * DHCPV6_RAW

        .. note:: The value for key ``value`` is the raw option value. The maximum supported
            characters are 65,536. When given as a ``str`` it will be passed to the DNS or DHCP
            service on the managed server verbatim.

        .. note:: The value for `name` is ignored when working with raw deployment options. Even if
            it is set in the structure, it will not be changed.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption

                option = APIDeploymentOption(
                    id=<entity_id>,
                    type=ObjectType.DNS_RAW_OPTION,
                    value="an-example-value",
                    properties={
                        "server": <server_id>,
                        <udf_name>: <udf_value>,
                    }
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_raw_deployment_option(option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateRawDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def get_deployment_options(
        self, entity_id: int, server_id: int, option_types: Optional[list] = None
    ) -> List[APIDeploymentOption]:
        """
        Get the deployment options for Address Manager DNS and DHCP services.

        :param entity_id: The object ID of the entity to which the DNS or DHCP deployment option is assigned.
        :type entity_id: int
        :param server_id: The specific server or server group to which options are deployed.
            The valid values are as follows:

            * server_id>0: Return only the options that are linked to the specified server ID.
            * server_id<0: Return all options regardless of the server ID specified.
            * server_id=0: Return only the options that are linked to all servers.
        :type server_id: int
        :param option_types: The list of deployment options types.
            If specified as an empty list, all deployment options for the specified entity will be returned.
            This value must be one of the following items:

                * DNSOption
                * DNSRawOption
                * DHCPRawOption
                * DHCPV6RawOption
                * DHCPV4ClientOption
                * DHCPV6ClientOption
                * DHCPServiceOption
                * DHCPV6ServiceOption
                * StartOfAuthority

        :type option_types: list
        :return: A list of APIDeploymentOptions
        :rtype: list[APIDeploymentOption]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                option_types = ["DNSOption", "DNSRawOption"]
                server_id = -1
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_options = client.get_deployment_options(<entity_id>, server_id, option_types)
                for deployment_option in deployment_options:
                    print(deployment_option.get('type'))

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        if option_types:
            option_types = option_types[0] if len(option_types) == 1 else "|".join(option_types)
        deployment_options = self.raw_api.getDeploymentOptions(entity_id, option_types, server_id)
        return list(map(APIDeploymentOption.from_raw_model, deployment_options))

    def add_dhcp6_service_deployment_option(
        self,
        entity_id: int,
        option_name: str,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DHCPv6 service option. DHCPv6 Service Deployment options can be assigned from the following levels:

            * Configuration
            * Server Group
            * Server
            * IPv6 block
            * IPv6 network
            * DHCPv6 range

        :param entity_id: The object ID of the entity to which the service option is being added.
        :type entity_id: int
        :param option_name: The name of the DHCPv6 service option. The name must be one of the following values:

                * client-updates
                * ddns-domainname
                * ddns-dual-stack-mixed-mode
                * ddns-guard-id-must-match
                * ddns-hostname
                * ddns-other-guard-is-dynamic
                * ddns-ttl
                * ddns-updates
                * ddns-update-style
                * default-lease-time
                * do-reverse-updates
                * limit-addresses-per-ia
                * preferred-lifetime
                * rapid-commit
                * server-preference
                * update-conflict-detection

        :type option_name: str
        :param value: The value assigned to the option.
        :type value: list
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new option.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    option_id = client.add_dhcp6_service_deployment_option(<configuration_id>, "ddns-updates", ["true"])
                print(option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP6ServiceDeploymentOption(
            entity_id, option_name, value, properties
        )

    def get_dhcp6_service_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ) -> APIDeploymentOption:
        """
        Get the DHCPv6 service option assigned to an object, excluding the options inherited
        from the higher-level parent objects.

        :param entity_id: The object ID of the entity to which the deployment option is assigned.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which the option is deployed for the specified entity.
            To retrieve an option that has not been assigned to a server role, set this value to zero.
        :type server_id: int
        :param option_name: The name of the DHCPv6 service option being retrieved.
            This name must be one of the constants listed for DHCPv6 client options.
        :type option_name: str
        :return: The requested DHCPv6 service option object.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                server_id = 0
                option_name = "ddns-updates"

                 with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcpv6_service = client.get_dhcp6_service_deployment_option(entity_id, server_id, option_name)
                print(dhcpv6_service)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIDeploymentOption.from_raw_model(
            self.raw_api.getDHCP6ServiceDeploymentOption(entity_id, option_name, server_id)
        )

    def update_dhcp6_service_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DHCPv6 service deployment option.

        .. note:: The Name field of the DHCPv6 service deployment option object cannot be updated.

        :param option: The DHCPv6 service option object to update.
        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import OptionType
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption

                option = APIDeploymentOption(
                    id=<entity_id>,
                    name="ddns-update-style",
                    type=OptionType.DHCP6_SERVICE,
                    value=["standard"],
                    properties={"inherited": "false"}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp6_service_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        self.raw_api.updateDHCP6ServiceDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def delete_dhcp6_service_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ):
        """
        Delete a DHCPv6 service deployment option.

        :param entity_id: The object ID of the entity from which this deployment option is being deleted.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which the option is deployed for the specified entity.
            To return an option that has not been assigned to a server role, set this value to 0 (zero)
        :type server_id: int
        :param option_name: The name of the DHCPv6 service option being deleted.
            This name must be one of the constants listed in BAM **DHCP client options**.
        :type option_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp6_service_deployment_option(entity_id, <server_id>, "ddns-updates")

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCP6ServiceDeploymentOption(entity_id, option_name, server_id)

    def add_dhcp6_client_deployment_option(
        self,
        entity_id: int,
        option_name: str,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DHCPv6 client option and return the database object ID of the new option object.

        .. note:: DHCPv6 Client Deployment options can be assigned from the following levels:

            * Configuration
            * Server Group
            * Server
            * IPv6 Block
            * IPv6 Network
            * DHCPv6 Range

        :param entity_id: The object ID of the entity to which the deployment option is being added.
        :type entity_id: int
        :param option_name: The name of the DHCPv6 client option being added.
            The name must be one of the following values:

                * dns-servers
                * domain-search-list
                * information-refresh-time
                * sntp-servers
                * unicast
                * wpad-url

        :type option_name: str
        :param value: The value assigned to the option.
        :type value: list[str]
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new DHCPv6 client object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                option_name = "information-refresh-time"
                value = ["9669"]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    object_id = client.add_dhcp6_client_deployment_option(entity_id, option_name, value)
                print(object_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP6ClientDeploymentOption(
            entity_id, option_name, value, properties
        )

    def get_dhcp6_client_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ) -> APIDeploymentOption:
        """
        Get a DHCPv6 client option assigned to an object, excluding the options inherited from
        the higher-level parent objects.

        :param entity_id: The object ID of the entity.
        :type entity_id: int
        :param server_id: The specific server or server group to which this option is deployed.
            To return an option that has not been assigned to a server role, set this value to zero.
        :type server_id: int
        :param option_name: The name of the DHCPv6 client option being added.
            This name must be one of the constants listed in BAM **DHCPv6 client options**.
        :type option_name: str
        :return: A DHCPv6 client option assigned to a specified object.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                option_name = "information-refresh-time"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    deployment_option = client.get_dhcp6_client_deployment_option(entity_id, <server_id>, option_name)
                print(deployment_option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIDeploymentOption.from_raw_model(
            self.raw_api.getDHCP6ClientDeploymentOption(entity_id, option_name, server_id)
        )

    def update_dhcp6_client_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DHCPv6 client options for entity.

        .. note:: The Name field of the DHCPv6 client deployment option object cannot be updated.

        :param option: The DHCPv6 client option is being updated.
        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption
                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import OptionType

                option = APIDeploymentOption(
                    id=<entity_id>,
                    name="information-refresh-time",
                    type=OptionType.DHCP6_CLIENT,
                    value=['3600'],
                    properties={"inherited": "false"}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp6_client_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDHCP6ClientDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def delete_dhcp6_client_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ):
        """
        Delete a DHCPv6 client option.

        :param entity_id: The object ID of the entity to which the client option is deleted.
        :type entity_id: int
        :param server_id: The specific server or server group to which this option is deployed.
            To return an option that has not been assigned to a server role, set this value to 0 (zero).
        :type server_id: int
        :param option_name: The name of the DHCPv6 client option deleted.
            This name must be one of the constants listed for DHCP6 client options.
        :type option_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCP6ClientDeploymentOptionType
                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <ip_network_id>
                option_name = DHCP6ClientDeploymentOptionType.INFORMATION_REFRESH_TIME

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp6_client_deployment_option(entity_id, <server_id>, option_name)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCP6ClientDeploymentOption(entity_id, option_name, server_id)

    def add_dhcp_client_deployment_option(
        self,
        entity_id: int,
        option_name: str,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DHCP client option.

        :param entity_id: The object ID of the entity to which the client option is added.
        :type entity_id: int
        :param option_name: The name of the DHCPv4 client option being added.
            This name must be one of the constants listed for DHCP client options.
        :type option_name: str
        :param value: The value assigned to the option.

            .. note:: Depending on the type of added DHCPv4 client option, the format of the value might differ.

        :type value: list[str]
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new DHCPv4 client option object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcpv4_client_id = client.add_dhcp_client_deployment_option(<ip4_block_id>, "time-offset", ['3600'])
                print(dhcpv4_client_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPClientDeploymentOption(entity_id, option_name, value, properties)

    def get_dhcp_client_deployment_option(
        self, entity_id: int, option_name: str, server_id: int
    ) -> APIDeploymentOption:
        """
        Get the DHCPv4 client option assigned to an object, excluding the options inherited from
        the higher-level parent objects.

        :param entity_id: The object ID of the entity to which the deployment option has been applied.
        :type entity_id: int
        :param option_name: The name of the DHCPv4 client option.
            This name must be one of the constants listed in BAM **DHCP client options**.
        :type option_name: str
        :param server_id: The specific server or server group to which this option is deployed.
            To return an option that has not been assigned to a server, set this value to 0 (zero).
        :type server_id: int
        :return: The DHCPv4 client option object assigned to the specified object.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcpv4_client = client.get_dhcp_client_deployment_option(<ip4_block_id>, "time-server", 0)
                print(dhcpv4_client)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        dhcpv4_client = self.raw_api.getDHCPClientDeploymentOption(
            entity_id, option_name, server_id
        )
        return APIDeploymentOption.from_raw_model(dhcpv4_client)

    def update_dhcp_client_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DHCP client option.

        .. note:: The name field of the DHCP client deployment option object cannot be updated.

        :param option: The DHCP client option object to update.
        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import OptionType

                option = APIDeploymentOption(
                    id=103709,
                    name="time-server",
                    type=OptionType.DHCP_CLIENT
                    value=['10.244.140.122', '10.244.140.124'],
                    properties={"inherited": "false"}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp_client_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDHCPClientDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def delete_dhcp_client_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ):
        """
        Delete a DHCP client deployment option.

        :param entity_id: The object ID of the entity from which the deployment option will be deleted.
        :type entity_id: int
        :param server_id: The specific server or server group to which this option is deployed.
            To delete an option that has not been assigned to a server, set this value to 0 (zero).
        :type server_id: int
        :param option_name: The name of the DHCPv4 client option to be deleted.
            This name must be one of the constants listed in BAM **DHCP client options**.
        :type option_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <ip4_block_id>
                option_name = "time-server"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp_client_deployment_option(entity_id, <server_id>, option_name)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCPClientDeploymentOption(entity_id, option_name, server_id)

    def add_dhcp_service_deployment_option(
        self,
        entity_id: int,
        option_name: str,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DHCP service option.

        :param entity_id: The object ID of the entity to which the service option is being added.
        :type entity_id: int
        :param option_name: The name of the DHCPv4 service option being added.
            This name must be one of the constants listed for DHCP service options.

            .. note:: If we do not configure the DDNS_UPDATE_STYLE service option, the default value is **interim**.

        :type option_name: str
        :param value: The value assigned to the option.

            .. note:: Depending on the type of deployment option, the format of the value input might differ.

        :type value: list[str]
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new DHCPv4 service option.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import (
                    DHCPServiceOption,
                    DHCPServiceOptionConstant
                )
                entity_id = <ip4_network_id>
                option_name = DHCPServiceOption.DDNS_HOSTNAME
                value = [
                    DHCPServiceOptionConstant.DDNS_HOSTNAME_TYPE_IP,
                    DHCPServiceOptionConstant.DDNS_HOSTNAME_POSITION_APPEND,
                    "10.0.0.10",
                ]
                properties = {"inherited": "false"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp_service_option_id = client.add_dhcp_service_deployment_option(
                        entity_id, option_name, value, properties
                    )
                print(dhcp_service_option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPServiceDeploymentOption(
            entity_id, option_name, value, properties
        )

    def get_dhcp_service_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ) -> APIDeploymentOption:
        """
        Get the DHCP service option assigned to an object, excluding the options inherited from
        the higher-level parent objects.

        :param entity_id: The object ID of the entity to which the deployment option is assigned.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which the option is deployed for the specified entity.
            To retrieve an option that has not been assigned to a server role, specify 0 as a value.
        :type server_id: int
        :param option_name: The name of the DHCPv4 service option being retrieved.
            This name must be one of the constants listed for DHCP service options.
        :type option_name: str
        :return: The requested DHCPv4 service option object from the database.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPServiceOption

                entity_id = <configuration_id>
                option_name = DHCPServiceOption.DDNS_DOMAINNAME

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp_service_option = client.get_dhcp_service_deployment_option(entity_id, 0, option_name)
                print(dhcp_service_option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        dhcp_service_option = self.raw_api.getDHCPServiceDeploymentOption(
            entity_id, option_name, server_id
        )
        return APIDeploymentOption.from_raw_model(dhcp_service_option)

    def update_dhcp_service_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DHCP service deployment option.

        :param option: The DHCP service deployment option object to be updated.

            .. note:: The name field of the DHCP service deployment option object cannot be updated.

        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import OptionType
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import (
                    DHCPServiceOption,
                    DHCPServiceOptionConstant,
                )

                option = APIDeploymentOption(
                    id=<option_id>,
                    name=DHCPServiceOption.DDNS_HOSTNAME,
                    type=OptionType.DHCP_SERVICE,
                    value=[
                        DHCPServiceOptionConstant.DDNS_HOSTNAME_TYPE_IP,
                        DHCPServiceOptionConstant.DDNS_HOSTNAME_POSITION_APPEND,
                        '10.0.0.10'
                    ],
                    properties={"inherited": "false"}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp_service_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDHCPServiceDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def delete_dhcp_service_deployment_option(
        self, entity_id: int, server_id: int, option_name: str
    ):
        """
        Delete a DHCP service deployment option.

        :param entity_id: The object ID of the object from which the deployment service is deleted.
        :type entity_id: int
        :param server_id: Specifies the server or server group to which the option is deployed for the specified entity.
            To retrieve an option that has not been assigned to a server role, set this value to 0 (zero).
            Omitting this parameter from the method call will result in an error.
        :type server_id: int
        :param option_name: The name of the DHCPv4 service option is deleted.
            This name must be one of the API constants listed for DHCP service options.
        :type option_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPServiceOption

                configuration_id = <configuration_id>
                server_id = <server_id>
                option_name = DHCPServiceOption.DDNS_DOMAINNAME

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp_service_deployment_option(configuration_id, server_id, option_name)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCPServiceDeploymentOption(entity_id, option_name, server_id)

    def add_dhcp_vendor_deployment_option(
        self,
        entity_id: int,
        option_id: int,
        value: Union[str, "list[str]", "list[list[str]]"],
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DHCP vendor deployment option to an object.

        :param entity_id: The object ID of the entity to which the DHCP vendor deployment option is added.
            This must be the ID of a Configuration, IP4Block, IP4Network, IP4NetworkTemplate, IPv4Address, IP4DHCPRange,
            Server, MACAddress, or MACPool.
        :type entity_id: int
        :param option_id: The object ID of the vendor option definition.
        :type option_id: int
        :param value: The value for the option. The value should be appropriate for its option type.
        :type value: list[str]
        :param properties: Object properties, including user-defined fields. This value can be empty.
            If the DHCP vendor client deployment option is intended for use with a specific server,
            the object ID of the server must be specified in the properties.
        :type properties: dict
        :return: The ID of the added DHCP vendor deployment option object.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                configuration_id = <configuration_id>
                vendor_option_id = <vendor_option_id>
                value = ['10.244.140.123']

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp_vendor_option_id = client.add_dhcp_vendor_deployment_option(
                        configuration_id, vendor_option_id, value
                    )
                print(dhcp_vendor_option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        value = serialize_possible_list(value)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPVendorDeploymentOption(entity_id, option_id, value, properties)

    def get_dhcp_vendor_deployment_option(
        self, entity_id: int, server_id: int, option_id: int
    ) -> APIDeploymentOption:
        """
        Get a DHCP vendor deployment option assigned to an object, excluding the options inherited from
        the higher-level parent objects.

        :param entity_id: The object ID of the entity to which the DHCP vendor deployment option is assigned.
            This must be the ID of a Configuration, IP4Block, IP4Network, IP4NetworkTemplate, IPv4Address, IP4DHCPRange,
            Server, MACAddress, or MACPool.
        :type entity_id: int
        :param server_id: The specific server or server group to which this option is deployed for the specified entity.
            To return an option that has not been assigned to a server, set this value to 0 (zero).
        :type server_id: int
        :param option_id: The object ID of the vendor option definition.
        :type option_id: int
        :return: An APIDeploymentOption for the DHCP vendor client deployment option.
        :rtype: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp_vendor_option = client.get_dhcp_vendor_deployment_option(entity_id, <server_id>, <option_id>)
                print(dhcp_vendor_option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIDeploymentOption.from_raw_model(
            self.raw_api.getDHCPVendorDeploymentOption(entity_id, option_id, server_id)
        )

    def update_dhcp_vendor_deployment_option(self, option: APIDeploymentOption):
        """
        Update a DHCP vendor deployment option.

        :param option: The DHCP vendor option object being updated.

            .. note:: The name field of the DHCP vendor deployment option object cannot be updated.

        :type option: APIDeploymentOption

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIDeploymentOption
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                option = APIDeploymentOption(
                    id=<ip4_network_id>,
                    name="test_option",
                    type=ObjectType.DHCP_VENDOR_CLIENT,
                    value=["test"],
                    properties={"server": <server_id>}
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_dhcp_vendor_deployment_option(option)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.updateDHCPVendorDeploymentOption(APIDeploymentOption.to_raw_model(option))

    def delete_dhcp_vendor_deployment_option(self, entity_id: int, server_id: int, option_id: int):
        """
        Delete a DHCP vendor deployment option.

        :param entity_id: The object ID of the object from which the DHCP vendor deployment option is being deleted.
        :type entity_id: int
        :param server_id: The object ID of the server or server group where the DHCP vendor deployment option is used.
            If the option is generic, set this value to 0 (zero).
        :type server_id: int
        :param option_id: The object ID of the vendor option definition.
        :type option_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_dhcp_vendor_deployment_option(entity_id, <server_id>, <option_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deleteDHCPVendorDeploymentOption(entity_id, option_id, server_id)

    def add_vendor_profile(
        self, name: str, identifier: str, description: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a vendor profile.

        :param name: An unique descriptive name for the vendor profile.
            This name is not matched against DHCP functionality.
        :type name: str
        :param identifier: An unique identifier sent by the DHCP client software running on a device.
        :type identifier: str
        :param description: A description of the vendor profile.
        :type description: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new vendor profile.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                identifier = "identifier_vendor_profile"
                description = "New vendor profile"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    vendor_id = client.add_vendor_profile("test_vendor", identifier, description)
                print(vendor_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addVendorProfile(identifier, name, description, properties)

    def add_vendor_option_definition(
        self,
        profile_id: int,
        option_id: int,
        option_name: str,
        type: str,
        description: str,
        allow_multiple: bool = False,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a vendor option definition to a vendor profile.

        :param profile_id: The object ID of the vendor profile.
        :type profile_id: int
        :param option_id: The deployment option ID. This value must be within the range of 1 to 254.
        :type option_id: int
        :param option_name: The name of the vendor option.
        :type option_name: str
        :param type: This type must be one of the constants listed for Vendor profile option types.
        :type type: str
        :param description: A description of the vendor option.
        :type description: str
        :param allow_multiple: Determines whether or not the custom option requires multiple values.
            The default value is false.
        :type allow_multiple: bool
        :param properties: Object properties, including user-defined fields. This value can be empty.
        :type properties: dict
        :return: The object ID of the new vendor option definition.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import VendorProfileOptionType

                profile_id = <vendor_profile_id>
                option_id = 12
                name = "test_vendor_option"
                type = VendorProfileOptionType.IP4
                description = "example vendor option"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    option_id = client.add_vendor_option_definition(
                        profile_id, option_id, name, type, description
                    )
                print(option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addVendorOptionDefinition(
            profile_id, option_id, option_name, type, description, allow_multiple, properties
        )

    def add_custom_option_definition(
        self,
        configuration_id: int,
        code: int,
        name: str,
        type: str,
        allow_multiple: bool = False,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a custom deployment option.

        :param configuration_id: The object ID of the configuration.
        :type configuration_id: int
        :param code: The option code for the custom deployment option.
            This value must be within the range of 151 to 174, 178 to 207, 212 to 219, 222 to 223, or 224 to 254.
        :type code: int
        :param name: The name of the custom deployment option.
        :type name: str
        :param type: The type of custom deployment option.
            This type must be one of the constants listed for DHCP custom option types.
        :type type: str
        :param allow_multiple: This parameter determines whether or not the custom option requires multiple values.
            The default value is false.
        :type allow_multiple: bool
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new option defined.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPCustomOptionType

                configuration_id = <configuration_id>
                code = 151
                name = "test-custom-option"
                type = DHCPCustomOptionType.TEXT

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    custom_option_id = client.add_custom_option_definition(
                        configuration_id, code, name, type
                    )
                print(custom_option_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addCustomOptionDefinition(
            configuration_id, name, code, type, allow_multiple, properties
        )

    # endregion Deployment Options

    # region User-defined Field

    def add_user_defined_field(self, object_type: str, udf: APIUserDefinedField):
        """
        Add a user-defined field for an object type.

        :param object_type: The object type that the field is defined for.
        :type object_type: str
        :param udf: The user-defined field to add.
        :type udf: APIUserDefinedField

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIUserDefinedField
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType, UserDefinedFieldType

                udf = APIUserDefinedField(
                    name="Unique UDF name",
                    displayName="UDF display name",
                    type=UserDefinedFieldType.TEXT,
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.add_user_defined_field(ObjectType.CONFIGURATION, udf)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        self.raw_api.addUserDefinedField(object_type, APIUserDefinedField.to_raw_model(udf))

    def update_user_defined_field(self, object_type: str, udf: APIUserDefinedField):
        """
        Update a user-defined field for an object type.

        :param object_type: The object type that the field is defined for.
        :type object_type: str
        :param udf: The user-defined field to update.
        :type udf: APIUserDefinedField

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import APIUserDefinedField
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType, UserDefinedFieldType

                udf = APIUserDefinedField(
                    name="Unique UDF name",
                    displayName="UDF display name",
                    type=UserDefinedFieldType.TEXT,
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_user_defined_field(ObjectType.CONFIGURATION, udf)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        self.raw_api.updateUserDefinedField(object_type, udf)

    def update_bulk_udf(
        self, data: Union[str, "list[list[Any]]", IO], properties: Optional[dict] = None
    ) -> dict:
        """
        Update value of various user-defined fields (UDFs) for different objects.

        :param data: A CSV string, two-dimensional list, or file with the following columns:

                #. **Entity Id** - The object ID of the entity on which the UDF needs to be updated.
                #. **UDF Name** - The actual name of the UDF that needs to be updated.
                #. **New UDF Value** - The new value of the UDF which needs to be updated on the
                   entity.

            .. note:: If you are using a CSV string or file, the input must not contain headers and
                ``data`` must start on the first line.

        :type data: str, list[list[Any]], IO
        :param properties: This is reserved for future use.
        :type properties: dict, optional
        :return: An empty dictionary is returned when all rows in the input data were successfully
            processed. If there were errors processing the input data, a dictionary is returned
            containing the following information:

            * **key** - The respective line number of CSV string or file; or the index of data as a
              list.
            * **value** - The reason for the failure identified by the system.

        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                data = "<entity_id>,<udf_name>,<new_udf_value>"

                # Update bulk UDF where input data as a string
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    result = client.update_bulk_udf(data)

                data = [
                    [<entity1_id>,<udf1_name>,<new_udf1_value>],
                    [<entity2_id>,<udf2_name>,<new_udf2_value>],
                ]

                # Update bulk UDF where input data as a list
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    result = client.update_bulk_udf(data)

                # Update bulk UDF where input data as an I/O stream
                with Client(<bam_host_url>) as client, open("test.csv", "rb") as file:
                    client.login(<username>, <password>)
                    result = client.update_bulk_udf(file)
                print(result)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        raw_data = data
        if isinstance(data, list):
            tmp_list = []
            for inner in data:
                x = ",".join(str(x) for x in inner)
                tmp_list.append(x)
            raw_data = "\n".join(tmp_list)
        properties = serialize_joined_key_value_pairs(properties)
        response = self.raw_api.updateBulkUdf(properties, raw_data)
        if not response:
            return {}
        result = {}
        for row in response.splitlines():
            number, message = row.split(",")
            number = int(number)
            if isinstance(data, list):
                number = number - 1
            result[number] = message
        return result

    def delete_user_defined_field(self, object_type: str, udf_name: str):
        """
        Delete user-defined field.

        :param object_type: The object type that the field is defined for.
        :type object_type: str
        :param udf_name: The name of the user-defined field.
        :type udf_name: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                udf_name = "unique-UDF-name"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_user_defined_field(ObjectType.CONFIGURATION, udf_name)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        self.raw_api.deleteUserDefinedField(object_type, udf_name)

    def get_user_defined_fields(
        self, object_type: str, required_fields_only: bool
    ) -> List[APIUserDefinedField]:
        """
        Get the user-defined fields defined for an object type.

        :param object_type: The object type that the fields are defined for.
        :type object_type: str
        :param required_fields_only: Whether all user-defined fields of the object type will be
            returned. If set to `True`, only required fields will be returned.
        :type required_fields_only: bool
        :return: The user-defined fields defined for an object type.
        :rtype: list[APIUserDefinedField]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    udfs = client.get_user_defined_fields(ObjectType.CONFIGURATION, False)
                print(udfs)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_1_0)
        data = self.raw_api.getUserDefinedFields(object_type, required_fields_only)
        data = list(map(APIUserDefinedField.from_raw_model, data))
        return data

    # endregion User-defined Field

    # region User-defined Link

    def add_user_defined_link(self, definition: UDLDefinition):
        """
        Add a new user-defined link definition.

        :param definition: The user-defined link to add.
        :type definition: UDLDefinition

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                definition = UDLDefinition(
                    linkType='<unique-UDL-type-name>',
                    displayName='<UDL-display-name>',
                    sourceEntityTypes'=["IP4Ranged", "IP4Network"],
                    destinationEntityTypes=["IP4Ranged", "IP4Block"],
                )
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.add_user_defined_link(definition)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        self.raw_api.addUserDefinedLink(UDLDefinition.to_raw_model(definition))

    def update_user_defined_link(self, definition: UDLDefinition):
        """
        Update a user-defined link for an object type.

        :param definition: The user-defined link to update.
        :type definition: UDLDefinition

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                definition = UDLDefinition(
                    linkType='<unique-UDL-type-name>',
                    displayName='<UDL-display-name>',
                    sourceEntityTypes'=["IP4Ranged", "IP4Network"],
                    destinationEntityTypes=["IP4Ranged", "IP4Block"],
                )
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_user_defined_link(definition)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        self.raw_api.updateUserDefinedLink(UDLDefinition.to_raw_model(definition))

    def delete_user_defined_link(self, link_type: str):
        """
        Delete the user-defined link definition.

        :param link_type: The link type that identifies a user-defined link definition.
        :type link_type: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_user_defined_link('<unique-UDL-type-name>')

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        link_type = dict(linkType=link_type)
        self.raw_api.deleteUserDefinedLink(json.dumps(link_type))

    def get_user_defined_link(self, link_type: str = "") -> List[UDLDefinition]:
        """
        Get a list of link definitions for a user-defined link type. The resulting list contains
        all link definitions when no link type is specified.

        :param link_type: The link type that identifies a user defined link definition.
        :type link_type: str
        :return: A list of link definitions from user-defined link type.
        :rtype: list[UDLDefinition]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    udls = client.get_user_defined_link('<unique-UDL-type-name>')
                for udl in udls:
                    print(udl.get('linkType'))

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        link_type = dict(linkType=link_type)
        raw_data = self.raw_api.getUserDefinedLink(json.dumps(link_type))
        udls = list(map(UDLDefinition.from_raw_model, raw_data))
        return udls

    # endregion User-defined Link

    # region UDL Relationship

    def link_entities_ex(self, relationship: UDLRelationship):
        """
        Establish a user-defined link between two Address Manager entities. The link has a
        direction - a source and a destination.

        :param relationship: The link type that identifies a user-defined link definition.
        :type relationship: UDLRelationship

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                relationship = UDLRelationship(
                    linkType="UniqueLinkTypeName",
                    sourceEntityId=256021,
                    destinationEntityId=256023,
                )
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.link_entities_ex(relationship)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return self.raw_api.linkEntitiesEx(UDLRelationship.to_raw_model(relationship))

    def unlink_entities_ex(self, relationship: UDLRelationship):
        """
        Remove a user-defined link between two Address Manager entities.

        :param relationship: The link type that identifies a user-defined link definition.
        :type relationship: UDLRelationship

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                relationship = UDLRelationship(
                    linkType="UniqueLinkTypeName",
                    sourceEntityId=256021,
                    destinationEntityId=256023,
                )
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.unlink_entities_ex(relationship)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return self.raw_api.unlinkEntitiesEx(UDLRelationship.to_raw_model(relationship))

    def get_linked_entities_ex(self, relationship: UDLRelationship) -> List[int]:
        """
        Get a list of entity IDs linked using the given link type to the given source or destination entity ID.

        :param relationship: The link type that identifies a user-defined link definition.
        :type relationship: UDLRelationship
        :return: A list of the IDs of the linked entities.
        :rtype: list[int]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                relationship = UDLRelationship(
                     linkType="UniqueLinkTypeName",
                     sourceEntityId=256021,
                )
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    linked_ids = client.get_linked_entities_ex(relationship)
                print(linked_ids)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return self.raw_api.getLinkedEntitiesEx(UDLRelationship.to_raw_model(relationship))

    # endregion UDL Relationship

    # region Server Services

    def get_server_services_configuration_status(self, configuration_token: str) -> dict:
        """
        Get the status of the services configuration task created using the configure_server_services
        API method.

        :param configuration_token: The object type that the fields are defined for.
        :type configuration_token: str
        :return: The service configuration status based on the token.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    resp = client.get_server_services_configuration_status(<configuration_token>)
                for k, v in resp.items():
                    print(f"{k}: {v}")

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return self._raw_api.getServerServicesConfigurationStatus(configuration_token)

    def get_server_services(self, id: int):
        """
        Get a description of the configured server services of a DNS/DHCP Server.

        :param id: The ID of the DNS/DHCP Server.
        :type id: int
        :return: A description of the configured server services. The returned value is the Address Manager's response
         as a Python dictionary.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    data = client.get_server_services(<id>)
                for name, value in data['services'].items():
                    print(name, value['configurations'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return self._raw_api.getServerServices(id)

    def configure_server_services(self, server_ids: list, configuration: dict) -> str:
        """
        Get a token value of the services configuration task.

        :param server_ids: The object IDs of the servers to configure.
        :type server_ids: list
        :param configuration: The configuration description of the services to be configured on the servers.
        :type configuration: dict
        :return: The token of the configuration indicating that the server(s) are configured with services based on the
         specified configuration.
        :rtype: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_ids = [2001, 2002, 2003]
                configuration = {
                    "version": "1.0.0",
                    "services": {
                        "ntp": {
                            "configurations": [
                                {
                                    "ntpConfiguration": {
                                        "enable": True,
                                        "servers": [
                                            {
                                                "address": "192.0.2.10",
                                                "stratum": "default"
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    token = client.configure_server_services(server_ids, configuration)
                print(token)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        token = self._raw_api.configureServerServices(",".join(map(str, server_ids)), configuration)
        return token

    # endregion Server Services

    # region IPv4 Template

    def add_ip4_template(
        self, configuration_id: int, template_name: str, properties: dict = None
    ) -> int:
        """
        Add an IPv4 template to a configuration.

        :param configuration_id: The object ID of the configuration where you wish to add the IPv4 template
        :type configuration_id: int
        :param template_name: The name of the IPv4 template
        :type template_name: str
        :param properties: A dictionary defining the IPv4 template properties. It includes the following keys:

            * gateway: An integer specifying which address to assign an IPv4 gateway.
              If it's a negative value, it counts from the end of the range.
            * reservedAddresses: A string specifying the reserved addresses details
        :type properties: dict
        :return: The object ID of the new IPv4 template.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                template_name = <ip4_template_name>
                reserved_addresses = (
                    '{RESERVED_DHCP_RANGE,OFFSET_AND_PERCENTAGE,'
                    '50,20,FROM_START,reserved_addresses_name,true}'
                )
                template_prop = {'gateway': 1, 'reservedAddresses': reserved_addresses}
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_template_id = client.add_ip4_template(<configuration_id>, template_name, template_prop)
                print(ip4_template_id)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4Template(configuration_id, template_name, properties)

    def assign_ip4_template(self, object_id: int, template_id: int, properties: dict = None):
        """
        Assign an IPv4 template to an IP4 Block, IP4 Network, DHCPv4 Range or DHCPv4 Address.

        :param object_id: The object ID of the IPv4 template recipient
        :type object_id: int
        :param template_id: The object ID of the IPv4 template
        :type template_id: int
        :param properties: A dict defining how the IPv4 template is assigned. It includes the following key:

            * overrideAssignedTemplate:  A string specifying should the previous assigned template
              is overridden. The default value is 'false'
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {'overrideAssignedTemplate': 'false'}
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.assign_ip4_template(<object_id>, <template_id>, properties)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.assignIP4Template(object_id, template_id, properties)

    def unassign_ip4_template(self, object_id: int, template_id: int, properties: dict = None):
        """
        Unassign an IPv4 template.

        :param object_id: The object ID of the IPv4 template recipient
        :type object_id: int
        :param template_id: The object ID of the IPv4 template
        :type template_id: int
        :param properties: Reserved for future use.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.unassign_ip4_template(<object_id>, <template_id>)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.unassignIP4Template(object_id, template_id, properties)

    def apply_ip4_template(self, object_id: int, template_id: int, properties: dict = None) -> str:
        """
        Apply an IPv4 Template.

        :param object_id: The object ID of the IPv4 template recipient.
            If the value is zero, the template is applied to all networks.
        :type object_id: int
        :param template_id: The object ID of the IPv4 template
        :type template_id: int
        :param properties: A dict defining what is applied.
            The option of any missing key will be ignored. The dict contains the following keys:

            * applyToNonConflictedNetworksOnly:  A string specifying if the template is applied
              only to a non-conflicted network. The default value is 'false'.
            * applyDeploymentOptions:  A string specifying if the template's deployment options
              are applied. The default value is 'false'.
            * applyReservedAddresses:  A string specifying if the template's
              reserved IPv4 addresses are applied. The default value is 'false'.
            * applyGateway:  A string specifying if the template's gateway offset is applied.
              The default value is 'false'.
            * applyDHCPRanges:  A string specifying if the template's DHCP ranges are applied.
              The default value is 'false'.
            * applyIPGroups:  A string specifying if the template's IP groups are applied.
              The default value is 'false'.
            * conflictResolutionOption: 'networkSettings' or 'templateSettings'.
              Specify which setting is taken in case of conflict.
              The default value is networkSettings.
            * convertOrphanedIPAddressesTo: 'STATIC' or 'DHCP RESERVED' or 'UNASSIGNED'.
              Specify what to convert orphaned IP addresses to. The default value is 'DHCP RESERVED'

        :type properties: dict
        :return: The task ID of the network template apply task
        :rtype: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {'applyToNonConflictedNetworksOnly': 'false',
                              'applyDeploymentOptions': 'true',
                              'applyReservedAddresses': 'true',
                              'applyGateway': 'true',
                              'applyDHCPRanges': 'true',
                              'applyIPGroups': 'true',
                              'conflictResolutionOption': 'templateSettings'
                              'convertOrphanedIPAddressesTo': 'UNASSIGNED'}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    task_id = client.apply_ip4_template(<object_id>, <template_id>, properties)
                print(task_id)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        if properties:
            properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.applyIP4Template(template_id, object_id, properties)

    def get_linked_ip4_object_conflicts(self, template_id: int, entity_id: int) -> dict:
        """
        Get a list of deployment options that conflict with the associated IPv4 objects,
        including networks, that are linked to the IPv4 template.

        :param template_id: The object ID of the IPv4 template.
        :type template_id: int
        :param entity_id: The object ID of the IPv4 object that is linked to the IPv4 template.
            Setting a value of zero returns all conflicting objects linked to the template.
        :type entity_id: int
        :return: A dictionary containing the conflicting network ranges and deployment options.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    conflicts = client.get_linked_ip4_object_conflicts(<template_id>, <entity_id>)
                print(conflicts)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return json.loads(self.raw_api.getLinkedIP4ObjectConflicts(template_id, entity_id))

    # endregion IPv4 Template

    # region IPv4 Objects

    def move_ip_object(self, entity_id: int, address: str, options: Optional[dict] = None) -> None:
        """
        Move an IPv4 block, IPv4 network, IPv4 address, IPv6 block, or IPv6 network to a new address.

        :param entity_id: The ID of the object. IPv4 blocks, IPv4 networks, IPv4 addresses, IPv6 blocks, and
            IPv6 networks are supported.
        :type entity_id: int
        :param address: The new address for the object.
        :type address: str
        :param options: A dictionary containing the following option:

            * **noServerUpdate** - A boolean value. If set to ``true``, instant dynamic host record changes will not be
              performed on DNS/DHCP Servers when moving an IPv4 address object.

              .. note:: **noServerUpdate** works only for an IPv4 address object.

        :type options: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                address = "10.0.0.0"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.move_ip_object(<ipv4_network_id>, address)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        self.raw_api.moveIPObject(entity_id, address, options)

    def resize_range(self, entity_id: int, range: str, options: Optional[dict] = None) -> None:
        """
        Change the size of an IPv4 block, IPv4 network, DHCPv4 range, IPv6 block, or IPv6 network.

        :param entity_id: The ID of the object to be resized. The method supports IPv4 block, IPv4
            network, DHCPv4 range, IPv6 block, and IPv6 network.
        :type entity_id: int
        :param range: The new size for the object to be resized.

            * For an IPv4 block and network, specify the size in CIDR notation or
              as an address range in the ``ipAddressStart-ipAddressEnd`` format.
            * For a DHCPv4 range, specify the size in the ``ipAddressStart-ipAddressEnd`` format.
            * For an IPv6 block and network, specify the size in the ``Starting address/Size``
              format.
        :type range: str
        :param options: A dictionary containing the following option:

            * **convertOrphanedIPAddressesTo**. The possible values are: **STATIC**, **DHCP_RESERVED**,
              **UNALLOCATED**. For example: ``options={"convertOrphanedIPAddressesTo": "STATIC"}``.

              .. note:: This option applies only to DHCPv4 range.

              * The default is **DHCP_RESERVED**.
              * If the option value is incorrect, an exception will be thrown.
              * If the option name is incorrect, the option will be ignored. Therefore, orphaned IP
                addresses will remain as assigned.
        :type options: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                range = "10.244.140.5-10.244.140.15"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.resize_range(<dhcp4_range_id>, range)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        self.raw_api.resizeRange(entity_id, range, options)

    # endregion IPv4 Objects

    # region IPv4 Templates

    def get_template_task_status(self, task_id: str) -> dict:
        """
        Get the status of the task for applying an IPv4 template.

        :param task_id: The ID of the task for applying an IPv4 template.
        :type task_id: str
        :return: Details about the task status and associated objects.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                task_id = "d596d7e3-682b-4155-80e8-f509f7cae78a"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    task_status = client.get_template_task_status(task_id)
                print(task_status)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        return json.loads(self.raw_api.getTemplateTaskStatus(task_id))

    # endregion IPv4 Templates

    # region IPv4 DHCP Ranges

    def add_dhcp4_range(
        self,
        network_id: int,
        start_address: str,
        end_address: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv4 DHCP range.

        :param network_id: The object ID of the IPv4 network in which the DHCP range is located.
        :type network_id: int
        :param start_address: An IP address defining the lowest address or start of the range.
        :type start_address: str
        :param end_address: An IP address defining the highest address or end of the range.
        :type end_address: str
        :param properties: Object properties, including the object name and user-defined fields.
        :type properties: dict
        :return: The object ID of the new DHCPv4 range.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                network_id = <network_id>
                start_address = "10.0.0.10"
                end_address = "10.0.0.13"
                properties = {"name": "ip4-dhcp-range"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp4_range_id = client.add_dhcp4_range(network_id, start_address, end_address, properties)
                print(dhcp4_range_id)

        .. versionadded:: 21.8.1
        """

        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP4Range(network_id, start_address, end_address, properties)

    def add_dhcp4_range_by_size(
        self, network_id: int, offset: int, size: int, properties: Optional[dict] = None
    ) -> int:
        """
        Add an IPv4 DHCP range by offset and percentage.

        :param network_id: The object ID of the IPv4 network in which the DHCP range is being located.
        :type network_id: int
        :param offset: An integer value specifying the point where the range should begin.

            * A positive value indicate the starting IP address of the range
              will be counted from the IPv4 Network first IP address and forward in the range.
            * A negative value indicate the starting IP address of the range
              will be counted from the IPv4 Network Broadcast Address last IP address and backward in the range.
        :type offset: int
        :param size: The size of the range.

            * If the value of defineRangeBy is "OFFSET_AND_SIZE",
              this value specify the number of addresses in the range.
            * If the value of defineRangeBy is "OFFSET_AND_PERCENTAGE",
              this value specify the range size in a relative size proportional to the parent network size.
        :type size: int
        :param properties: Object properties, including the object name,
            user-defined fields, and the value of defineRangeBy.

            * The possible values for defineRangeBy are "OFFSET_AND_SIZE" and "OFFSET_AND_PERCENTAGE".
            * The default value for defineRangeBy is "OFFSET_AND_SIZE".
        :type properties: dict
        :return: The object ID of the new DHCPv4 range.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPDefineRange

                network_id = <ip4_network_id>
                offset = <offset_number>
                size = 4
                properties = {"defineRangeBy": DHCPDefineRange.OFFSET_AND_PERCENTAGE}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    dhcp4_range_id = client.add_dhcp4_range_by_size(network_id, offset, size, properties)
                print(dhcp4_range_id)

        .. versionadded:: 21.8.1
        """

        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP4RangeBySize(network_id, offset, size, properties)

    def get_max_allowed_range(self, range_id: int) -> list[str]:
        """
        Find the maximum possible address range to which the existing IPv4 DHCP range can be
        extended. This method only supports the IPv4 DHCP range.

        :param range_id: The object ID of the IPv4 DHCP range.
        :type range_id: int
        :return: The possible start address and end address for the specified IPv4 DHCP range.
        :rtype: list[str]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    max_allowed_range = client.get_max_allowed_range(<range_id>)
                print(max_allowed_range)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        return self.raw_api.getMaxAllowedRange(range_id)

    # endregion IPv4 DHCP Ranges

    # region IPv6 DHCP Ranges

    def add_dhcp6_range(
        self,
        network_id: int,
        start_address: str,
        end_address: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv6 DHCP range.

        :param network_id: The object ID of the network in which this DHCPv6 range is being located.
        :type network_id: int
        :param start_address: An IP address defining the lowest address or start of the range.
        :type start_address: str
        :param end_address: An IP address defining the highest address or end of the range.
        :type end_address: str
        :param properties: Object properties, including the object name and user-defined fields.
        :type properties: dict
        :return: The object ID of the new DHCPv6 range.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                network_id = <network_id>
                start_address = "2000::1"
                end_address = "2000::64"
                properties = {"name": "test-dhcp6-range"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    object_id = client.add_dhcp6_range(network_id, start_address, end_address, properties)
                print(object_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP6Range(network_id, start_address, end_address, properties)

    def add_dhcp6_range_by_size(
        self, ip6_network_id: int, start: str, size: int, properties: Optional[dict] = None
    ) -> int:
        """
        Add an IPv6 DHCP range by size.

        :param ip6_network_id: The object ID of the network in which the DHCP range is being located.
        :type ip6_network_id: int
        :param start: An empty string, an positive integer, or IPv6 address specifying the point where
            the range should begin.

            .. note::

                * If defineRangeBy is set with the AUTOCREATE_BY_SIZE value in the property field,
                  the start field must contain an empty string ("").
                * If defineRangeBy is set with the OFFSET_AND_SIZE value in the property field,
                  the start field must contain a positive integer value that indicates the starting IP address of
                  the range will be counted from Network address and forward in the range.
                * If defineRangeBy is set with the START_ADDRESS_AND_SIZE value in the property field,
                  the start field must contain a valid IPv6 address that will be used as the starting address of
                  the DHCP range.

        :type start: str
        :param size: The size of the range. Currently, the range size is only specified in
            a relative size proportional to the parent network size.
        :type size: int
        :param properties: Object properties, including the following options: the object name,
            the value of defineRangeBy, and user-defined fields. The possible values for defineRangeBy are
            AUTOCREATE_BY_SIZE, OFFSET_AND_SIZE, and START_ADDRESS_AND_SIZE.

            .. note:: If the defineRangeBy value isn't specified, the DHCP range will be created using
                AUTOCREATE_BY_SIZE by default.

        :type properties: dict
        :return: The object ID of the new DHCPv6 range.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPDefineRange
                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                start = "2"
                size = 3
                properties = {"name": "dhcp6-range", "defineRangeBy": DHCPDefineRange.OFFSET_AND_SIZE}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity_id = client.add_dhcp6_range_by_size(<ip6_network_id>, start, size, properties)
                print(entity_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCP6RangeBySize(ip6_network_id, start, size, properties)

    # endregion IPv6 DHCP Ranges

    # region Audit Log

    def get_audit_log_export_status(self) -> dict:
        """
        Get the audit data export settings that were set using the configure_audit_log_export API method.

        :return: The current audit data export settings in Address Manager.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    settings = client.get_audit_log_export_status()
                for k, v in settings.items():
                    print(f"{k}: {v}")

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        return json.loads(self.raw_api.getAuditLogExportStatus())

    def configure_audit_log_export(self, audit_log_settings: dict):
        """
        Configure the audit data export service to an external database, either a Splunk server or an HTTP endpoint.

        .. attention:: This API method requires the following:

            * If you enter an HTTPS endpoint in the Output URI or Healthcheck URI field
              when configuring HTTP output or Host field when configuring Splunk output, you must select this
              check box and enter TLS information.

        :param audit_log_settings: The data for Audit data settings.
        :type audit_log_settings: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                audit_log_settings = {
                    "sinks": [{"healthCheck": False, "type": "http", "uri": "http://localhost:9900"}],
                    "enable": True,
                }
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.configure_audit_log_export(audit_log_settings)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        self.raw_api.configureAuditLogExport(audit_log_settings)

    def update_retention_settings(
        self, settings: Optional[RetentionSettings] = None
    ) -> RetentionSettings:
        """
        Set the new value for history retention settings and return the existing values.

        :param settings: The history retention settings.
        :type settings: RetentionSettings
        :return: RetentionSettings
        :rtype: RetentionSettings

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.api.models import RetentionSettings

                # To get existing retention settings value
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    retention_settings = client.update_retention_settings()

                # To update history retention settings which administrative history is 1(day),
                session event history is 3(days), DDNS history is 2(days) and DHCP history is 2(days)
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    retention_settings = client.update_retention_settings(
                        RetentionSettings(admin=1, sessionEvent=3, ddns=2, dhcp=2)
                    )
                print('Administrative retention history:', retention_settings['admin'])

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        settings = (
            RetentionSettings.to_raw_model(settings)
            if settings
            else RetentionSettings.to_raw_model(dict())
        )
        raw_data = self.raw_api.updateRetentionSettings(**settings)
        return RetentionSettings.from_raw_model(raw_data)

    # endregion Audit Log

    # region DNS Response Policies

    def add_response_policy(
        self,
        configuration_id: int,
        name: str,
        type: str,
        ttl: int,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a DNS response policy.

        :param configuration_id: The object ID of the configuration to which the response policy is being added.
        :type configuration_id: int
        :param name: The name of the DNS response policy.
        :type name: str
        :param type: This type must be one of the constants for Response policy types.
        :type type: str
        :param ttl: The time-to-live (TTL) value in seconds.
        :type ttl: int
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new DNS response policy.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ResponsePolicy

                configuration_id = <configuration_id>
                name = <policy_name>
                type = ResponsePolicy.BLACKLIST
                ttl = 300

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    policy_id = client.add_response_policy(configuration_id, name, type, ttl)
                print(policy_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addResponsePolicy(configuration_id, name, type, ttl, properties)

    def add_response_policy_item(
        self, policy_id: int, absolute_name: str, options: Optional[list] = None
    ) -> bool:
        """
        Add a DNS response policy item under a local DNS response policy.

        :param policy_id: The object ID of the parent local response policy to which
            the response policy item is being added.
        :type policy_id: int
        :param absolute_name: The FQDN of the response policy item.
        :type absolute_name: str
        :param options: Reserved for future use.
        :type options: list
        :return: A boolean value indicating whether the Response policy item is added.
        :rtype: bool

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                policy_id = <policy_id>
                absolute_name = <policy_item_name>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    status = client.add_response_policy_item(policy_id, absolute_name)
                print(status)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        options = serialize_joined_values(options)
        return self.raw_api.addResponsePolicyItem(policy_id, absolute_name, options)

    def delete_response_policy_item(
        self, policy_id: int, absolute_name: str, options: Optional[list] = None
    ):
        """
        Delete a DNS response policy item under a local DNS response policy.

        :param policy_id: The object ID of the parent local response policy to which
            the response policy item is being deleted.
        :type policy_id: int
        :param absolute_name: The FQDN of the response policy item.
        :type absolute_name: str
        :param options: Reserved for future use.
        :type options: list
        :raises ErrorResponse: When response policy item is not found.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                policy_id = <policy_id>
                absolute_name = <policy_name.policy_item_name>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.delete_response_policy_item(policy_id, absolute_name)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        options = serialize_joined_values(options)
        parameters = {"policyId": policy_id, "itemName": absolute_name, "options": options}
        response = self._raw_api.session.delete(
            self._raw_api._service.url  # pylint: disable=protected-access
            + "/deleteResponsePolicyItem",
            params=parameters,
            verify=self._raw_api.session.verify,
        )
        status = _wadl_parser.process_rest_response(response)
        if status != 1:
            raise ErrorResponse(f"Object was not found: {absolute_name}", response)

    def search_response_policy_items(
        self,
        scope: str,
        keyword: str,
        properties: Optional[dict] = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> list:
        """
        Search Response Policy items configured in local Response Policies or predefined BlueCat Security feed data.
        The search will return a list of all matching items in Address Manager across all configurations.

        :param scope: The scope in which the search is to be performed.

            * **Local** - to search policy items configured in local Response Policies.
            * **Feed** - to search policy items configured in predefined BlueCat Security Feed data.
            * **All** - to search policy items configured in both local Response Policies and
              predefined BlueCat Security Feed data.

        :type scope: str
        :param keyword: The search string for which you wish to search.

            * **^** - matches the beginning of a string. For example: **^ex** matches **ex**\\ ample but not t\\ **ex**\\ t.
            * **$** - matches the end of string. For example: **ple$** matches exam\\ **ple** but not **ple**\\ ase.
            * ***** - matches zero or more characters within a string. For example: **ex*t** matches **ex**\\ i\\ **t** and **ex**\\ cellen\\ **t**.

        :type keyword: str
        :param properties: Reserved for future use.
        :type properties: dict
        :param start: A starting number from where the search result will be returned.
            The possible value is a positive integer ranging from 0 to 999.
        :type start: int
        :param count: The total number of results to return.
            The possible value is a positive integer ranging from 1 to 1000.
        :type count: int
        :return: A list of ResponsePolicySearchResult objects.
            Each object contains information of one Response Policy item found either in local Response Policies
            or BlueCat Security feed data.
        :rtype: list[ResponsePolicySearchResult]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                # Using local Response Policies scope
                scope = "Local"
                keyword = "^te*"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    policy_items = client.search_response_policy_items(scope, keyword)
                for policy_item in policy_items:
                    print(policy_item)

        .. versionadded:: 21.5.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        policy_items = self.raw_api.searchResponsePolicyItems(
            keyword, scope, start, count, properties
        )
        return list(map(ResponsePolicySearchResult.from_raw_model, policy_items))

    def upload_response_policy_file(self, parent_id: int, data: Union[str, IO]) -> dict:
        """
        Upload one response policy file containing a list of fully qualified domain names (FQDNs).

        :param parent_id: The object ID of the parent response policy under which the response
            policy item is being uploaded.
        :type parent_id: int
        :param data: The file or a string to be uploaded under the response policy.

            .. note:: The size of the content should not be more than 75 MB.

        :type data: str, IO
        :return: An empty dictionary is returned when all rows in the input data were uploaded
            successfully. Otherwise, a dictionary containing the respective lines from the input
            data and the reason they were skipped.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                # Upload response policy items where input data as an I/O stream.
                with Client(<bam_host_url>) as client, open("test.txt", "rb") as file:
                    client.login(<username>, <password>)
                    result = client.upload_response_policy_file(<policy_id>, file)
                print(result)

                # Upload response policy items where input data as a string.
                data = "www.example.com"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    result = client.upload_response_policy_file(<policy_id>, data)
                print(result)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_3_0)
        response = self.raw_api.uploadResponsePolicyFile(parent_id, data)
        if not response:
            return {}
        result = {}
        for row in response.splitlines():
            invalid_item, message = row.split(",")
            result[invalid_item] = message
        return result

    # endregion DNS Response Policies

    # region Groups and Users

    def add_user(self, username: str, password: str, properties: dict) -> int:
        """
        Add an Address Manager user.

        :param username: The name of the user.
        :type username: str
        :param password: The Address Manager password for the user.
            The password must be set even if the authenticator property option is defined.
        :type password: str
        :param properties: Object properties. It includes user-defined fields and options listed in List of options:

            * authenticator: The object ID of the external authenticator defined in Address Manager.
            * securityPrivilege: A security privilege type for non-administrative users with GUI, API, or GUI and
              API access. The valid values are listed in User security privileges.

              .. note:: NO_ACCESS is the default value.

            * historyPrivilege: A history privilege type for non-administrative users with GUI or GUI and API access.
              The valid values are: HIDE or VIEW_HISTORY_LIST.

              .. note:: HIDE is the default value.

            * email: The user's email address (required).
            * phoneNumber: The user's phone number (optional).
            * userType: ADMIN or REGULAR

              .. note:: REGULAR represents a non-administrative user and is the default value.

            * userAccessType: API, GUI, or GUI_AND_API (required).

        :type properties: dict
        :return: The object ID of the new Address Manager user.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {
                    "email": "myemail@mail.com",
                    "userAccessType": "GUI"
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    user_id = client.add_user(<new_username>, <user_password>, properties)
                print(user_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addUser(username, password, properties)

    def add_user_group(self, group_name: str, properties: Optional[dict] = None) -> int:
        """
        Add a user group.

        :param group_name: The name of the user group.
        :type group_name: str
        :param properties: A dictionary defining the User Groups' properties. It includes the following key:

            * isAdministrator: either true or false,
              to indicate whether or not you wish to add an administrator user group to Address Manager.

        :type properties: dict
        :return: The object ID of the new Address Manager user group.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                group_name = <user_group_name>
                properties = {"isAdministrator": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    user_group_id = client.add_user_group(group_name, properties)
                print(user_group_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addUserGroup(group_name, properties)

    def update_user_password(self, user_id: int, password: str, options: Optional[list] = None):
        """
        Update an Address Manager user password. The user must be an Address Manager administrator to invoke this method.

        :param user_id: The user ID of an application user who is either a primary or a secondary authenticator.
        :type user_id: int
        :param password: The new password for the user.
            The password must be set even if the authenticator property option is defined.
        :type password: str
        :param options: Reserved for future use.
        :type options: list

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                user_id = <user_id>
                password = 'ChooseApassword@123'
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.update_user_password(user_id, password)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        options = serialize_joined_values(options)
        self.raw_api.updateUserPassword(user_id, password, options)

    def terminate_user_sessions(self, username: str, properties: Optional[dict] = None):
        """
        Terminate all active user sessions in Address Manager.

        :param username: The username of the user for which all active sessions are terminated.
        :type username: str
        :param properties: Reserved for future use.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.terminate_user_sessions(<username>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.terminateUserSessions(username, properties)

    # endregion Groups and Users

    # region MAC Addresses

    def add_mac_address(
        self, configuration_id: int, mac_address: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a MAC address.

        :param configuration_id: The object ID of the parent configuration in which the MAC address is being added.
        :type configuration_id: int
        :param mac_address: The MAC address as a 12-digit hexadecimal in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn,
            or nn:nn:nn:nn:nn:nn.
        :type mac_address: str
        :param properties: Object properties and user-defined fields. The properties may include:

            * ``name`` - A name for the MAC address.
            * ``macPool`` - The object ID of the parent MAC pool.

        :type properties: dict
        :return: The object ID of the new MAC address.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                mac_address = "09-08-07-06-05-04"
                properties = {"name": "mac-address-name", "macPool": <mac_pool_id>, <UDF_name>: <UDF_value>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    mac_address_id = client.add_mac_address(<configuration_id>, mac_address, properties)
                print(mac_address_id)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addMACAddress(configuration_id, mac_address, properties)

    def get_mac_address(self, configuration_id: int, mac_address: str) -> APIEntity:
        """
        Get a MAC address object by the address value.

        :param configuration_id: The object ID of the configuration in which the MAC address is located.
        :type configuration_id: int
        :param mac_address: The MAC address as a 12-digit hexadecimal in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn, or
            nn:nn:nn:nn:nn:nn.
        :type mac_address: str
        :return: An object with the MAC address data. Returns ``None`` if the MAC address cannot be found.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                mac_address = "2C:54:91:88:C9:E3"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    mac_object = client.get_mac_address(<configuration_id>, mac_address)
                print(mac_object)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        mac_object = self.raw_api.getMACAddress(configuration_id, mac_address)
        return APIEntity.from_raw_model(mac_object)

    def deny_mac_address(self, configuration_id: int, mac_address: str):
        """
        Deny a MAC address by assigning it to the DENY MAC Pool. If a MAC address object does not exist for that MAC
        address, it will be created.

        :param configuration_id: The object ID of the parent configuration in which the MAC address resides.
        :type configuration_id: int
        :param mac_address: The MAC address as a 12-digit hexadecimal in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn, or
            nn:nn:nn:nn:nn:nn.
        :type mac_address: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                mac_address = "2C:54:91:88:C9:E3"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.deny_mac_address(<configuration_id>, mac_address)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.denyMACAddress(configuration_id, mac_address)

    def associate_mac_address_with_pool(
        self, configuration_id: int, mac_pool_id: int, mac_address: str
    ):
        """
        Associate a MAC address with a MAC pool. If a MAC address object does not exist for that MAC address, it
        will be created.

        :param configuration_id: The object ID of the parent configuration in which the MAC address resides.
        :type configuration_id: int
        :param mac_pool_id: The object ID of the MAC pool with which this MAC address is associated.
        :type mac_pool_id: int
        :param mac_address: The MAC address as a 12-digit hexadecimal in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn,
            or nn:nn:nn:nn:nn:nn.
        :type mac_address: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                mac_address = "1C:12:28:08:09:87"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.associate_mac_address_with_pool(<configuration_id>, <mac_pool_id>, mac_address)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.associateMACAddressWithPool(configuration_id, mac_address, mac_pool_id)

    # endregion MAC Addresses

    # region IPv4 Addresses

    def assign_ip4_address(
        self,
        configuration_id: int,
        ip4_address: str,
        action: str,
        mac_address: Optional[str] = None,
        host_info: Optional[list] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Assign a MAC address and other properties to an IPv4 address.

        :param configuration_id: The object ID of the configuration in which the IPv4 address is located.
        :type configuration_id: int
        :param ip4_address: The IPv4 address.
        :type ip4_address: str
        :param action: This parameter must be one of the constants of IP assignment action values.
        :type action: str
        :param mac_address: The MAC address to assign to the IPv4 address.
            The MAC address can be specified in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn or nn:nn:nn:nn:nn:nn,
            where nn is a hexadecimal value.
        :type mac_address: str
        :param host_info: A list containing host information for the address with the following format:
         [hostname,viewId,reverseFlag,sameAsZoneFlag]. Where:

          * hostname - The FQDN of the host record to be added.
          * viewId - The object ID of the view under which this host should be created.
          * reverseFlag - The flag indicating if a reverse record should be created. The possible values are
            true or false.
          * sameAsZoneFlag - The flag indicating if record should be created as same as zone record.
            The possible values are true or false.

        :type host_info: list
        :param properties: A dictionary containing the following property, including user-defined fields:

            * ptrs - a string containing the list of unmanaged external host records to be associated
              with the IPv4 address in the format: viewId,exHostFQDN[, viewId,exHostFQDN,...]
            * name - name of the IPv4 address.
            * locationCode - the hierarchical location code consists of a set of 1 to 3 alpha-numeric strings
              separated by a space. The first two characters indicate a country, followed by next three characters
              which indicate a city in UN/LOCODE. New custom locations created under a UN/LOCODE city are appended
              to the end of the hierarchy. For example, CA TOR OF1 indicates: CA= Canada TOR=Toronto OF1=Office 1.
            * allowDuplicateHost (optional) - duplicate hostname check option.
              There are three possible values for this property:

                * Enable - set to enable the property and refuse duplicate hostnames.
                * Disable - set to disable the property and allow duplicate hostnames.
                * Inherit - set to make the hostname use the option specified in the higher-level parent object.

                .. note:: Disable is the default value for allowDuplicateHost.

            * pingBeforeAssign (optional) - specifies whether Address Manager performs a ping check
              before assigning the IP address. The property can be one of the following values:

                * enable - specifies that Address Manager performs a ping check before assigning the IP address.
                * disable - specifies that Address Manager will not perform a ping check before assigning the IP address.

        :type properties: dict
        :return: The object ID of the newly assigned IPv4 address.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import IPAssignmentActionValues

                configuration_id = <configuration_id>
                ip4_address = <ip4_address>
                action = IPAssignmentActionValues.MAKE_STATIC
                mac_address = <mac_address>
                host_info = [<existing_host_name>, <view_id>, "false", "true"]
                properties = {"locationCode": "CA"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_address_id = client.assign_ip4_address(
                        configuration_id,
                        ip4_address,
                        action,
                        mac_address,
                        host_info,
                        properties,
                    )
                print(ip4_address_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        host_info = serialize_joined_values(host_info)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.assignIP4Address(
            configuration_id, ip4_address, mac_address, host_info, action, properties
        )

    def assign_next_available_ip4_address(
        self,
        configuration_id: int,
        entity_id: int,
        action: str,
        mac_address: Optional[str] = None,
        host_info: Optional[list] = None,
        properties: Optional[dict] = None,
    ) -> APIEntity:
        """
        Assign the next available IPv4 address. Assign a MAC address and other properties to the next available
        and unallocated IPv4 address within a configuration, block, or network.

        :param configuration_id: The object ID of the configuration in which the IPv4 address is located.
        :type configuration_id: int
        :param entity_id: The object ID of the configuration, block, or network in which
            to look for the next available address.
        :type entity_id: int
        :param action: This parameter must be one of the constants of IP assignment action values.
        :type action: str
        :param mac_address: The MAC address to assign to the IPv4 address.
            The MAC address can be specified in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn or nn:nn:nn:nn:nn:nn,
            where nn is a hexadecimal value.
        :type mac_address: str
        :param host_info: A list containing host information for the address in the following format:
         [hostname, viewId, reverseFlag, sameAsZoneFlag]. Where:

            * hostname - The FQDN of the host record to be added.
            * viewId - The object ID of the view under which this host should be created.
            * reverseFlag - The flag indicating if a reverse record should be created.
              The possible values are true or false.
            * sameAsZoneFlag - The flag indicating if record should be created as same as zone record.
              The possible values are true or false.

        :type host_info: list
        :param properties: Object properties.
        :type properties: dict
        :return: The APIEntity for the newly assigned IPv4 address.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import IPAssignmentActionValues

                configuration_id = <configuration_id>
                entity_id = <ip4_network_id>
                action = IPAssignmentActionValues.MAKE_STATIC
                mac_address = <mac_address>
                host_info = [<existing_host_name>, <view_id>, "false", "true"]
                properties = {"locationCode": "CA", "skip": "10.0.1.8,10.0.1.9", "allowDuplicateHost": "Enable"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_address = client.assign_next_available_ip4_address(
                        configuration_id,
                        entity_id,
                        action,
                        mac_address,
                        host_info,
                        properties,
                    )
                print(ip4_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        host_info = serialize_joined_values(host_info)
        properties = serialize_joined_key_value_pairs(properties)
        ip4_address = self.raw_api.assignNextAvailableIP4Address(
            configuration_id, entity_id, mac_address, host_info, action, properties
        )
        return APIEntity.from_raw_model(ip4_address)

    def change_state_ip4_address(
        self, id: int, target_state: str, mac_address: Optional[str] = None
    ):
        """
        Convert the state of an address from and between Reserved, DHCP Reserved, and Static,
        or DHCP Allocated to DHCP Reserved.

        :param id: The object ID of the address of which the state is being changed .
        :type id: int
        :param target_state: One of MAKE_STATIC, MAKE_RESERVED, MAKE_DHCP_RESERVED.
        :type target_state: str
        :param mac_address: Optional and only needed, if the target requires it. For example, MAKE_DHCP_RESERVED.
            The MAC address to assign to the IPv4 address. The MAC address can be specified in the format nnnnnnnnnnnn,
            nn-nn-nn-nn-nn-nn or nn:nn:nn:nn:nn:nn, where nn is a hexadecimal value.
        :type mac_address: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import IPAssignmentActionValues

                id = <ip4_address_id>
                target_state = IPAssignmentActionValues.MAKE_DHCP_RESERVED
                mac_address = "00-1B-45-01-5A-B7"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.change_state_ip4_address(id, target_state, mac_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.changeStateIP4Address(id, target_state, mac_address)

    def get_next_available_ip4_address(self, entity_id: int) -> str:
        """
        Get the IPv4 address for the next available (unallocated) address within a configuration, block, or network.

        :param entity_id: The object ID of configuration, block, or network in which the next available address
            is being retrieving.
        :type entity_id: int
        :return: The next available IPv4 address in an existing network.
        :rtype: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    available_ip4_address = client.get_next_available_ip4_address(<entity_id>)
                print(available_ip4_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return self.raw_api.getNextAvailableIP4Address(entity_id)

    def get_ip4_address(self, entity_id: int, address: str) -> APIEntity:
        """
        Get the details for the requested IPv4 address object.

        :param entity_id: The object ID of the configuration, block, network, or DHCP range in which
         the address is being located.
        :type entity_id: int
        :param address: The IPv4 address.
        :type address: str
        :return: The requested IPv4 Address object.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <ip4_network_id>
                address = "10.0.0.10"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    address_entity = client.get_ip4_address(entity_id, address)
                print(address_entity)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getIP4Address(entity_id, address))

    def get_next_ip4_address(self, entity_id: int, properties: Optional[dict] = None) -> str:
        """
        Get the next available IP address in octet notation under specified circumstances.

        :param entity_id: The object ID of the configuration or network in which the address is located.
        :type entity_id: int
        :param properties: Contain three properties skip, offset and excludeDHCPRange.
            The values for skip and offset must be IPv4 addresses and must appear in dotted octet notation.

            * skip - This is optional. It is used to specify the IP address ranges or IP addresses to skip,
              separated by comma. A hyphen (-), not a dash is used to separate the start and end addresses.
            * offset - This is optional. This is to specify from which address to start to assign IPv4 Address.
            * excludeDHCPRange - This specifies whether IP addresses in DHCP ranges should be excluded from assignment.
              The value is either true or false, default value is false.

            .. note:: Do not use the skip property with IP address ranges if the entity id is a configuration id.
              If you do, an error message appears, `Skip is not allowed for configuration level`.

        :type properties: dict
        :return: The IPv4 address in octet notation.
        :rtype: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {"offset": "10.0.0.1", "excludeDHCPRange": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_address = client.get_next_ip4_address(<ip4_network_id>, properties)
                print(ip4_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.getNextIP4Address(entity_id, properties)

    def is_address_allocated(
        self, configuration_id: int, ip_address: str, mac_address: str
    ) -> bool:
        """
        Query a MAC address to determine if the address has been allocated to an IP address.

        :param configuration_id: The object ID of the configuration in which the MAC address resides.
        :type configuration_id: int
        :param ip_address: The IPv4 DHCP allocated address to be checked against the MAC address.
        :type ip_address: str
        :param mac_address: The MAC address in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn or nn:nn:nn:nn:nn:nn,
         where nn is a hexadecimal value.
        :type mac_address: str
        :return: A Boolean value indicating whether the address is allocated.
        :rtype: bool

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                configuration_id = <configuration_id>
                ip_address = "10.0.0.10"
                mac_address = "00-60-56-9B-29-9B"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    is_allocated = client.is_address_allocated(configuration_id, ip_address, mac_address)
                print(is_allocated)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return self.raw_api.isAddressAllocated(configuration_id, ip_address, mac_address)

    # endregion IPv4 Addresses

    # region IPv4 Group

    def add_ip4_ip_group_by_size(
        self,
        ip4_network_id: int,
        name: str,
        size: int,
        position_range_by: Optional[str] = None,
        position_value: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv4 IP group by size.

        :param ip4_network_id: The object ID of the network in which the IP group is being added.
        :type ip4_network_id: int
        :param name: The name of the IP group.
        :type name: str
        :param size: The number of addresses in the IP group.
        :type size: int
        :param position_range_by: A string specifying the position of the IP group range in the parent network.
            This is optional. The value must be one of the constants listed for IP group range position.
        :type position_range_by: str
        :param position_value: The offset value when using START_OFFSET or END_OFFSET.
            The start address of the IP group in the network when using START_ADDRESS.
            This is required only if position_range_by is specified.
        :type position_value: str
        :param properties: Object properties, including the user-defined fields.
        :type properties: dict
        :return: The object ID of the new IPv4 IP group.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import IPGroupRangePosition

                ip4_network_id = <ip4_network_id>
                name = <ip_group_name>
                size = 10
                position_range_by = IPGroupRangePosition.START_ADDRESS
                position_value = "10.0.0.20"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip_group_id = client.add_ip4_ip_group_by_size(
                        ip4_network_id, name, size, position_range_by, position_value
                    )
                print(ip_group_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4IPGroupBySize(
            ip4_network_id, name, size, position_range_by, position_value, properties
        )

    def add_ip4_ip_group_by_range(
        self,
        ip4_network_id: int,
        name: str,
        start_address: str,
        end_address: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv4 IP group by range bound.

        :param ip4_network_id: The object ID of the network in which the IP group is being added.
        :type ip4_network_id: int
        :param name: The name of the IP group.
        :type name: str
        :param start_address: A start IPv4 address of the IP group range.
        :type start_address: str
        :param end_address: An end IPv4 address of the IP group range.
        :type end_address: str
        :param properties: Object properties, including the user-defined fields.
        :type properties: dict
        :return: The object ID of the new IPv4 IP group.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                ip4_network_id = <ip4_network_id>
                name = <ip_group_name>
                start_address = "10.0.0.1"
                end_address = "10.0.0.20"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip_group_id = client.add_ip4_ip_group_by_range(
                        ip4_network_id, name, start_address, end_address
                    )
                print(ip_group_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4IPGroupByRange(
            ip4_network_id, name, start_address, end_address, properties
        )

    # endregion IPv4 Group

    # region IPv4 Networks

    def add_ip4_network(
        self, ip4_block_id: int, cidr: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add an IPv4 network using CIDR notation.

        :param ip4_block_id: The object ID of the IPv4 block in which the IPv4 network is being added.
        :type ip4_block_id: int
        :param cidr: The CIDR notation defining the network, for example: 10.10.10/24.
        :type cidr: str
        :param properties: Object properties. For more information about the available options, refer to IPv4 objects.
        :type properties: dict
        :return: The object ID of the new IPv4 network.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                ip4_block_id = <ip4_block_id>
                cidr = "10.10.10/24"
                properties = {"name": "ip4-network-name", "defaultView": <existing_view_id>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_network_id = client.add_ip4_network(ip4_block_id, cidr, properties)
                print(ip4_network_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4Network(ip4_block_id, cidr, properties)

    def get_next_available_ip4_network(
        self, entity_id: int, size: int, is_larger_allowed: bool, auto_create: bool
    ) -> int:
        """
        Get the object ID of the next available (unused) network within a configuration or block.

        :param entity_id: The object ID of the network's parent object.
        :type entity_id: int
        :param size: The size of the network, expressed as a power of 2.
            The size represents the number of hosts on the network.
            For example, if a /24 network is created or searched for, the size would be 256.
        :type size: int
        :param is_larger_allowed: This Boolean value indicates whether to return larger networks than
            those specified with the size parameter.
        :type is_larger_allowed: bool
        :param auto_create: This Boolean value indicates whether the next available network should be created
            if it does not exist.
        :type auto_create: bool
        :return: The object ID of the existing next available IPv4 network or,
            if the next available network did not exist and auto_create was set to true, the newly created IPv4 network.
            if the next available network did not exist and auto_create was set to false, the method will return 0.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                ip4_block_id = <ip4_block_id>
                size = 4
                is_larger_allowed = False
                auto_create = True

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_network_id = client.get_next_available_ip4_network(
                        ip4_block_id, size, is_larger_allowed, auto_create
                    )
                print(ip4_network_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return self.raw_api.getNextAvailableIP4Network(
            entity_id, size, is_larger_allowed, auto_create
        )

    def get_next_available_ip_range(
        self, parent_id: int, size: int, type: str, properties: Optional[dict] = None
    ) -> APIEntity:
        """
        Get the next available (unused) block or network within a configuration or block.
        If no existing range can be returned, a new one may be requested to be created if there's enough space.

        :param parent_id: The object ID of the parent object under which the next available range resides.
        :type parent_id: int
        :param size: The size of the range. Must be an integer power of 2.
        :type size: int
        :param type: The object type of the requested range. The method supports IPv4 blocks and networks.
        :type type: str
        :param properties: Additional options of the operation:

            * **reuseExisting** - A boolean value to indicate whether to search existing empty networks to find the
              requested range. The default value is false. If both ``reuseExisting`` and
              ``autoCreate`` are defined, ``reuseExisting`` takes precedence over ``autoCreate``.
            * **isLargerAllowed** - A boolean value to indicate whether to return larger networks than
              those specified with the size parameter. The default value is false.
            * **autoCreate** - A boolean value to indicate whether the next available IP range should be created in
              the parent object if it does not exist. The default value is the opposite value of ``reuseExisting``.
            * **traversalMethod** - The algorithm used to find the next available range.
              Defaults to DEPTH_FIRST. The possible values are:

                * NO_TRAVERSAL - will attempt to find the next range directly under the specified parent object.
                  It will not search through to the lower level objects.
                * DEPTH_FIRST - will attempt to find the next range under the specified object by iterating through
                  its children one by one. After exploring the object recursively for its child ranges,
                  it will move to the next child object.
                * BREADTH_FIRST - will attempt to find the next range under the specified object by iterative levels.
                  It will first find the range immediately below the specified parent object.
                  If not found, then it will attempt to find the range under all the first child objects.

        :type properties: dict, optional
        :return: An object representing the existing next available IP range, or a newly created IP range
            if the next available range does not exist and ``autoCreate`` was set to true.
            ``None`` if the next available range does not exist and ``autoCreate`` was set to false.
        :rtype: APIEntity
        :raises ErrorResponse: ``autoCreate`` was set to true, but there isn't enough space to create a range of
            the requested size in the containing entity.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType, TraversalMethod

                parent_id = <ip4_block_id>
                properties = {
                    "reuseExisting": "true",
                    "traversalMethod": TraversalMethod.NO_TRAVERSAL
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    available_ip4_network = client.get_next_available_ip_range(
                        parent_id, 128, ObjectType.IP4_NETWORK, properties
                    )
                print(available_ip4_network)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return APIEntity.from_raw_model(
            self.raw_api.getNextAvailableIPRange(parent_id, size, type, properties)
        )

    def get_next_available_ip_ranges(
        self,
        parent_id: int,
        type: str,
        count: int,
        size: int,
        properties: Optional[dict] = None,
    ) -> list[APIEntity]:
        """
        Get a list of the next available (unused) networks within a configuration or block.
        If no existing ranges can be returned, a new list of IP ranges may be requested to be
        created if there's enough space.

        :param parent_id: The object ID of the parent object under which the next available range
            resides.
        :type parent_id: int
        :param type: The object type of the requested range. This method supports IPv4 networks.
        :type type: str
        :param count: The number of IP ranges to be found.

            .. note:: If this value is greater than 1:

                * The ``isLargerAllowed`` property will not be applicable.

        :type count: int
        :param size: The size of the range. Must be an integer power of 2.
        :type size: int
        :param properties: Additional options of the operation:

            * **reuseExisting** - A boolean value to indicate whether to search existing empty
              networks to find the requested range. The default value is ``false``.
              If both ``reuseExisting`` and ``autoCreate`` are defined, ``reuseExisting`` takes
              precedence over ``autoCreate``.
            * **isLargerAllowed** - A boolean value to indicate whether to return larger networks
              than those specified with the size parameter. The default value is ``false``.
            * **autoCreate** - A boolean value to indicate whether the next available IP ranges
              should be created in the parent object if they do not exist already.
              The default value is the opposite value of ``reuseExisting``.
            * **traversalMethod** - The algorithm used to find the next available ranges.
              Defaults to ``DEPTH_FIRST``. The possible values are:

                * NO_TRAVERSAL - will attempt to find the next range directly under the specified
                  parent object. It will not search through to the lower level objects.
                * DEPTH_FIRST - will attempt to find the next range under the specified object by
                  iterating through its children one by one. After exploring the object recursively
                  for its child ranges, it will move to the next child object.
                * BREADTH_FIRST - will attempt to find the next range under the specified object by
                  iterative levels. It will first find the range immediately below the specified
                  parent object. If not found, then it will attempt to find the range under all
                  the first child objects.

                .. note:: Only ``DEPTH_FIRST`` supports finding multiple available ranges.

        :type properties: dict, optional
        :return: A list of objects representing the next existing available IP ranges or
            the newly created IP ranges if the next available IP ranges do not exist and
            ``autoCreate`` was set to ``true``. Returns an empty list if the next available ranges
            do not exist and ``autoCreate`` was set to ``false``.
        :rtype: list[APIEntity]
        :raises ErrorResponse: ``autoCreate`` was set to ``true``, but there is not enough space to
            create a range of the requested size in the containing entity.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                parent_id = <ip4_block_id>
                properties = {"reuseExisting": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    available_ip4_networks = client.get_next_available_ip_ranges(
                        parent_id, ObjectType.IP4_NETWORK, 4, 64, properties
                    )
                print(available_ip4_networks)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        available_ip4_ranges = self.raw_api.getNextAvailableIPRanges(
            parent_id, size, type, count, properties
        )
        return [APIEntity.from_raw_model(ip4_range) for ip4_range in available_ip4_ranges]

    def split_ip4_network(
        self, network_id: int, number_of_parts: int, options: Optional[dict] = None
    ) -> list:
        """
        Split an IPv4 network into the specified number of networks.

        :param network_id: The object ID of the network that is being split.
        :type network_id: int
        :param number_of_parts: The number of the networks into which the network is being split.
            Valid values are 2, 4, 8, 16, 32, 64, 128, 256, 512, or 1024.
        :type number_of_parts: int
        :param options: Additional options of the operation:

            * **assignDefaultGateway** - a boolean value. If set to **true**, each network will have a default gateway
              created using the first IP address in that network. The default value is **true**.
            * **overwriteConflicts** - a boolean value. If set to **true**, any conflicts within the split IPv4 network
              will be removed. The default value is **false**.
            * **preserveGateway** - a boolean value. If set to **true**, the gateway in the original network
              will be preserved. The default value is **true**.
            * **template** - a network template ID. Specify a network template ID if it is applied.
              The default value is zero (0) which means no network template will be used.

        :type options: dict, optional
        :return: A list of networks after splitting the network.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                options = {"assignDefaultGateway": "false", "template": <template_id>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_networks = client.split_ip4_network(<ip4_network_id>, 4, options)
                print(ip4_networks)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        ip4_ranges = self.raw_api.splitIP4Network(network_id, number_of_parts, options)
        return [APIEntity.from_raw_model(ip4_range) for ip4_range in ip4_ranges]

    # endregion IPv4 Networks

    # region Shared Networks

    def share_network(self, network_id: int, tag_id: int) -> None:
        """
        Link an IPv4 network with a shared network tag. To use shared networks, you must create
        a tag and tag group, and associate the tag group with a configuration. A configuration can
        have multiple associated tags but only one tag is required for creating a shared network.

        :param network_id: The object ID of the IPv4 network that is being linked with a shared
            network tag.
        :type network_id: int
        :param tag_id: The object ID of the tag that is linked.
        :type tag_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.share_network(<network_id>, <tag_id>)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.shareNetwork(network_id, tag_id)

    def unshare_network(self, ip4_network_id: int) -> None:
        """
        Unlink the shared network tag from an IPv4 network.

        :param ip4_network_id: The object ID of the IPv4 network that is being unlinked from
            a shared network tag.
        :type ip4_network_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.unshare_network(<ip4_network_id>)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.unshareNetwork(ip4_network_id)

    # endregion Shared Networks

    # region IPv6 Addresses

    def add_ip6_address(
        self,
        entity_id: int,
        address: str,
        type: str,
        name: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv6 address to an IPv6 Network.

        :param entity_id: The object ID of the entity where the IPv6 address is being added.
            This can be the object ID of a Configuration, IPv6 Block, or IPv6 Network.
        :type entity_id: int
        :param address: The IPv6 address. Address and type must be consistent.
        :type address: str
        :param type: The type of IPv6 address.
            This value must be one of the following: MACAddress, IP6Address, or InterfaceID.
        :type type: str
        :param name: The descriptive name for the IPv6 address. This value can be empty.
        :type name: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the new IPv6 address.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                entity_id = <entity_id>
                address = <ip6_address>
                type = ObjectType.IP6_ADDRESS
                name = "ipv6-address-name"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity_id = client.add_ip6_address(entity_id, address, type, name)
                print(entity_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP6Address(entity_id, address, type, name, properties)

    def get_ip6_address(self, entity_id: int, address: str) -> APIEntity:
        """
        Get an IPv6 address object.

        :param entity_id: The object ID of the entity that contains the IPv6 address.
            The entity can be a Configuration, IPv6 Block, or IPv6 Network.
        :type entity_id: int
        :param address: The IPv6 address.
        :type address: str
        :return: An IPv6 address object. The value is `None` if the IPv6 address does not exist.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <entity_id>
                address = <ip6_address>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_address = client.get_ip6_address(entity_id, address)
                print(ip6_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getIP6Address(entity_id, address))

    def get_ip6_objects_by_hint(
        self,
        container_id: int,
        type: str,
        options: Optional[dict] = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> List[APIEntity]:
        """
        Get a list of IPv6 objects found under a given container object.
        The networks can be filtered by using hint and accessRight options.
        Only supports IPv6 Networks.

        :param container_id: The object ID of the container object.
            It can be the object ID of any object in the parent object hierarchy.
            The highest parent object is the configuration level.
        :type container_id: int
        :param type: The type of object containing the IPv6 Network. Currently, it only supports IP6Network.
        :type type: str
        :param options: A dictionary containing the following options:

            * hint: The values for the hint option can be the prefix of the IP address for a network
              or the name of a network.
            * accessRight: The values for the accessRight option must be one of the constants listed for
              Access right values and Object types. If the Access right value isn't specified,
              the View access level will be used by default.

        :type options: dict
        :param start: Indicate where in the list of objects to start returning objects.
            The list begins at an index of 0.
        :type start: int
        :param count: Indicate the maximum number of child objects that this method will return.
            The default value is 10.
        :type count: int
        :return: A list of IPv6 objects based on the input arguments,
            or return an empty list if the ID of the container object is invalid.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AccessRightValues

                container_id = <entity_id>
                type = ObjectType.IP6_NETWORK
                options = {"hint": <prefix_IPv6_address>, "accessRight": AccessRightValues.AddAccess}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_objects = client.get_ip6_objects_by_hint(container_id, type, options)
                print(ip6_objects)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        ip6_objects = self.raw_api.getIP6ObjectsByHint(container_id, type, start, count, options)
        return list(map(APIEntity.from_raw_model, ip6_objects))

    def get_next_available_ip6_address(
        self,
        entity_id: int,
        properties: Optional[dict] = None,
    ) -> List[str]:
        """
        Get a list of the next available IPv6 addresses within an IPv6 Block or Network.

        :param entity_id: The object ID of IPv6 Block or Network where the next available IPv6 addresses is requested.
        :type entity_id: int
        :param properties: Object properties, containing the following optional properties:

            * startOffset - An integer that specifies from which offset to retrieve the available IPv6 address(es).
              The valid value ranges from 0 to 2 ^ 63 (2 to the power of 63).
            * skip - Specifies the IPv6 address ranges or IPv6 addresses to skip, separated by a comma.
            * includeDHCPRanges - A boolean that specifies whether DHCP ranges should be included
              when retrieving the next available IPv6 address. The default value is false.
            * numberOfAddresses - An integer that is the number of requested IPv6 addresses. The default value is 1.
              The valid value is from 1 to 100. All IPv6 addresses will be returned from a single network.

        :type properties: dict
        :return: A list of available IPv6 addresses in an existing IPv6 Block or Network.
        :rtype: list[str]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <ip6_network_id>
                properties = {
                    "numberOfAddresses": 5,
                    "skip": <skip_addresses>,
                    "includeDHCPRanges": "False",
                    "startOffset": 100,
                )

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    available_ip6_addresses = client.get_next_available_ip6_address(entity_id, properties)
                for available_ip6_address in available_ip6_addresses:
                    print(available_ip6_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self._require_minimal_version(_version.V9_2_0)
        properties = serialize_joined_key_value_pairs(properties)
        available_ip6_addresses = self.raw_api.getNextAvailableIP6Address(entity_id, properties)
        return available_ip6_addresses.strip("[]").replace(" ", "").split(",")

    def clear_ip6_address(self, id: int):
        """
        Clear an IPv6 address assignment.

        :param id: The object ID of the IPv6 address to unassign.
        :type id: int
        :raises ErrorResponse: When BAM fails to clear IPv6 address.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.clear_ip6_address(<id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        response = self._raw_api.session.delete(
            self._raw_api._service.url + "/clearIP6Address",  # pylint: disable=protected-access
            params={"addressId": id},
            verify=self._raw_api.session.verify,
        )
        status = _wadl_parser.process_rest_response(response)
        if not status:
            raise ErrorResponse(f"Failed to clear IPv6 address: {id}", response)

    def add_ip6_block_by_mac_address(
        self,
        parent_ip6_block_id: int,
        mac_address: str,
        name: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv6 Block by a MAC address.

        :param parent_ip6_block_id: The object ID of the parent object to which the IPv6 block is being added.
            The entity must be another IPv6 Block.
        :type parent_ip6_block_id: int
        :param mac_address: The MAC address in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn,
            or nn:nn:nn:nn:nn:nn, where nn is a hexadecimal value.
        :type mac_address: str
        :param name: The descriptive name for the IPv6 block. This value can be empty.
        :type name: str
        :param properties: Object properties, including user-defined fields. This value can be empty.
        :type properties: dict
        :return: The object ID of the new IPv6 Block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                parent_ip6_block_id = <ip6_block_id>
                mac_address = "00:1B:44:11:3A:B7"
                name = "ip6-address-name"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity_id = client.add_ip6_block_by_mac_address(parent_ip6_block_id, mac_address, name)
                print(entity_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP6BlockByMACAddress(
            parent_ip6_block_id, mac_address, name, properties
        )

    def add_ip6_block_by_prefix(
        self,
        parent_ip6_block_id: int,
        prefix: str,
        name: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv6 Block by specifying the prefix for the block.

        :param parent_ip6_block_id: The object ID of the entity to which the IPv6 address is being
            added. The entity is another IPv6 Block.
        :type parent_ip6_block_id: int
        :param prefix: The IPv6 prefix for the new block.
        :type prefix: str
        :param name: The descriptive name for the IPv6 Block. This value can be empty.
        :type name: str
        :param properties: Object properties, including user-defined fields. This value can be empty.
        :type properties: dict
        :return: The object ID of the new IPv6 Block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                ip6_block_id = <parent_ip6_block_id>
                prefix = "2001::/64"
                name = "ipv6-block-name"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_block_id = client.add_ip6_block_by_prefix(ip6_block_id, prefix, name)
                print(ip6_block_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP6BlockByPrefix(parent_ip6_block_id, prefix, name, properties)

    def add_ip6_network_by_prefix(
        self,
        ip6_block_id: int,
        prefix: str,
        name: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add an IPv6 Network by specifying the prefix for the network.

        :param ip6_block_id: The object ID of the IPv6 Block in which the new IPv6 Network is being located.
        :type ip6_block_id: int
        :param prefix: The IPv6 prefix for the new network.
        :type prefix: str
        :param name: The descriptive name for the IPv6 Network. This value can be empty.
        :type name: str
        :param properties: Object properties, including user-defined fields. This value can be empty.
        :type properties: dict
        :return: The object ID of the new IPv6 Network.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                prefix = "2001::/64"
                name = "ipv6-network-name"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_network_id = client.add_ip6_network_by_prefix(<ip6_block_id>, prefix, name)
                print(ip6_network_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP6NetworkByPrefix(ip6_block_id, prefix, name, properties)

    def get_entity_by_prefix(self, container_id: int, prefix: str, type: str) -> APIEntity:
        """
        Get an IPv6 address of an IPv6 Block or Network.

        :param container_id: The object ID of higher-level parent object IPv6 Block or
            Configuration in which the IPv6 Block or Network is being located.
        :type container_id: int
        :param prefix: The prefix value for the IPv6 Block or Network.
        :type prefix: str
        :param type: The type of object. The only supported object types are IP6Block and IP6Network.
        :type type: str
        :return: An APIEntity for the specified IPv6 Block or Network.
            The APIEntity is empty if the IPv6 Block or Network does not exist.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                container_id = <global_ip6_block_id>
                prefix = "2001::/64"
                type = ObjectType.IP6_BLOCK

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_block = client.get_entity_by_prefix(container_id, prefix, type)
                print(ip6_block)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getEntityByPrefix(container_id, prefix, type))

    def assign_ip6_address(
        self,
        entity_id: int,
        address: str,
        action: str,
        mac_address: Optional[str] = None,
        host_info: Optional[list] = None,
        properties: Optional[dict] = None,
    ) -> bool:
        """
        Assign an IPv6 address to a MAC address and host.

        :param entity_id: The object ID of the entity in which the IPv6 address is being assigned.
            This can be the object ID of a Configuration, IPv6 Block, or IPv6 Network.
        :type entity_id: int
        :param address: The IPv6 address.
            The address must be created with addIP6Address before it can be assigned.
        :type address: str
        :param action: This parameter determines how to assign the address.
            Valid value is MAKE_STATIC or MAKE_DHCP_RESERVED.
        :type action: str
        :param mac_address: The MAC address in the format nnnnnnnnnnnn, nn-nn-nn-nn-nn-nn, or nn:nn:nn:nn:nn:nn,
            where nn is a hexadecimal value.
        :type mac_address: str
        :param host_info: The host information for the IPv6 address. This value can be empty.
            The host_info string uses the following format: viewId, hostname, ifSameAsZone, ifReverseMapping
        :type host_info: list
        :param properties: Object properties, including user-defined fields, this value can be empty,
            containing the following properties:

            * ptrs - A string containing the list of unmanaged external host records to be associated
              with the IPv6 address in the format: viewId,exHostFQDN[, viewId,exHostFQDN,...]
            * name - The name of the IPv6 address.
            * locationCode - The hierarchical location code consists of a set of 1 to 3 alpha-numeric strings
              separated by a space. The first two characters indicate a country, followed by next three characters
              which indicate a city in UN/LOCODE. New custom locations created under a UN/LOCODE city are appended
              to the end of the hierarchy. For example, CA TOR OF1 indicates: CA = Canada TOR = Toronto OF1 = Office 1.
            * reserveUsing - Defines the type of reservation, if through Client DUID or MAC Address.
              Applicable only for DHCP Reserved IP Addresses.
              If this value is not defined, the system defaults to Client DUID.
            * DUID - The DHCPv6 unique identifier.

        :type properties: dict
        :return: True if the IPv6 address is successfully assigned,
            return False if the address is not successfully assigned.
        :rtype: bool

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import IPAssignmentActionValues

                entity_id = <ip6_block_id>
                ip6_address = <ipv6_address>
                action = IPAssignmentActionValues.MAKE_STATIC
                mac_address = <MAC_address>
                host_info = [<view id>, "www.example.com", "false", "true"]
                properties = {"name": "ip6-address-name", "locationCode": "CA"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    assigned_ip6_address = client.assign_ip6_address(
                        entity_id, ip6_address, action, mac_address, host_info, properties
                    )
                print(assigned_ip6_address)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        host_info = serialize_joined_values(host_info)
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.assignIP6Address(
            entity_id, address, action, mac_address, host_info, properties
        )

    def reassign_ip6_address(
        self,
        old_address_id: int,
        destination: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Reassign an existing IPv6 address to a new IPv6 address.

        :param old_address_id: The object ID of the IPv6 address to reassign.
        :type old_address_id: int
        :param destination: The destination of the reassigned address.
            This can be an IPv6 address or a MAC address from which the new IPv6 address is being calculated.
            Specify the MAC address in the format nnnnnnnnnnnn or nn-nn-nn-nn-nn-nn, where nn is a hexadecimal value.
        :type destination: str
        :param properties: Object properties, including user-defined fields.
        :type properties: dict
        :return: The object ID of the reassigned IPv6 address.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                old_address_id = <old_address_id>
                destination = "2000:33::3"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_address_id = client.reassign_ip6_address(old_address_id, destination)
                print(ip6_address_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.reassignIP6Address(old_address_id, destination, properties)

    def split_ip6_range(
        self, entity_id: int, number_of_parts: int, options: Optional[dict] = None
    ) -> List[APIEntity]:
        """
        Split an IPv6 block or network into a number of blocks or networks.

        :param entity_id: The object ID of the block or network that is being split.
        :type entity_id: int
        :param number_of_parts: The number of the blocks or networks into which the block or network is being split.
            Valid values are 2, 4, 8, 16, 32, 64, 128, 256, 512, or 1024.
        :type number_of_parts: int
        :param options: No options available. Reserved for future use.
        :type options: dict
        :return: A list of the IPv6 blocks or networks created after splitting the block or network.
        :rtype: list[APIEntity]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip6_blocks = client.split_ip6_range(<ip6_block_id>, 2)
                print(ip6_blocks)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        options = serialize_joined_key_value_pairs(options)
        ip6_addresses = self.raw_api.splitIP6Range(entity_id, number_of_parts, options)
        return list(map(APIEntity.from_raw_model, ip6_addresses))

    # endregion IPv6 Addresses

    # region Servers

    def add_server(
        self,
        configuration_id: int,
        name: str,
        default_interface_address: str,
        absolute_name: str,
        profile: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a server to Address Manager.

        :param configuration_id: The object ID of the configuration to which the server is being added.
        :type configuration_id: int
        :param name: The name of the server to add.
        :type name: str
        :param default_interface_address: The physical IP address for the server within Address Manager.
        :type default_interface_address: str
        :param absolute_name: The DNS FQDN by which the server is referenced.
        :type absolute_name: str
        :param profile: The server capability profile. The profile describes the type of server or
         appliance being added and determines the services that can be deployed to this server.
         This must be one of the constants found in Server capability profiles.
        :type profile: str
        :param properties: Object properties, a dictionary including the following options:

            * **connected** - either true or false; indicates whether or not to connect to a server.
              In order to add and configure multi-port DNS/DHCP Servers, this option must be set to true.
              If false, other interface property options will be ignored.
            * **upgrade** - indicates whether or not to apply the latest version of DNS/DHCP Server software once
              the appliance is under Address Manager control. The value is either true or false, by default, false.
            * **password** - the server password. For more information on the default server password,
              refer to BlueCat default login credentials (This must be authenticated to view this topic).
            * **servicesIPv4Address** - IPv4 address used only for services traffic such as DNS, DHCP, DHCPv6, and TFTP.
              If dedicated management is enabled, this option must be specified.
            * **servicesIPv4Netmask** - IPv4 netmask used only for services traffic such as DNS, DHCP, DHCPv6, and TFTP.
              If dedicated management is enabled, this option must be specified.
            * **servicesIPv6Address** - IPv6 address used only for services traffic such as DNS, DHCP, DHCPv6, and TFTP.
              This is optional.
            * **servicesIPv6Subnet** - IPv6 subnet used only for services traffic such as DNS, DHCP, DHCPv6, and TFTP.
              This is optional.
            * **xhaIPv4Address** - IPv4 address used for XHA. This is optional.
            * **xhaIPv4Netmask** - IPv4 netmask used for XHA. This is optional.
            * **redundancyScenario** - networking redundancy scenarios. The possible values are ACTIVE_BACKUP Failover
              and IEEE_802_3AD Load Balancing.

            .. note:: For DNS/DHCP Servers without multi-port support, the interface-related property options will be ignored.

        :type properties: dict
        :return: The object ID of the new server.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ServerCapabilityProfiles

                configuration_id = <configuration_id>
                name = "server-name"
                default_interface_address = <ip_address>
                absolute_name = "example.com"
                profile = ServerCapabilityProfiles.ADONIS_1200
                properties = {"connected": "false"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    server_id = client.add_server(
                        configuration_id, name, default_interface_address, absolute_name, profile, properties
                    )
                print(server_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addServer(
            configuration_id, name, default_interface_address, absolute_name, profile, properties
        )

    def deploy_server_config(self, server_id: int, properties: dict):
        """
        Deploy specific configuration(s) to a particular server.

        :param server_id: The object ID of the server to deploy immediately.
        :type server_id: int
        :param properties: Object properties. The values for properties are:

            * services - The valid service configuration to deploy.
              These are the valid values for the services: DNS, DHCP, DHCPv6, and TFTP.
            * forceDNSFullDeployment - A boolean value. Set to true to perform a full DNS deployment.

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_id = <server_id>
                properties = {"services": "DNS", "forceDNSFullDeployment": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.deploy_server_config(server_id, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.deployServerConfig(server_id, properties)

    def deploy_server_services(self, server_id: int, services: list):
        """
        Deploy specific service(s) to a particular server.

        :param server_id: The object ID of the server to deploy services to.
        :type server_id: int
        :param services: The names of the valid services to deploy.
        :type services: list

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_id = <server_id>
                services = ["DNS", "DHCP"]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.deploy_server_services(server_id, services)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        services = serialize_joined_values(services)
        self.raw_api.deployServerServices(server_id, services)

    def get_server_deployment_status(
        self, server_id: int, properties: Optional[dict] = None
    ) -> int:
        """
        Get the deployment status of a server.

        :param server_id: The object ID of the server whose deployment status needs to be checked.
        :type server_id: int
        :param properties: The valid value is empty.
        :type properties: dict
        :return: The status code for deployment of a particular server.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    status_code = client.get_server_deployment_status(<server_id>)
                print(status_code)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.getServerDeploymentStatus(server_id, properties)

    def get_deployment_task_status(self, task_token: str) -> dict:
        """
        Get the deployment status of the deployment task that was created using the selectiveDeploy API method.

        :param task_token: The string token value that is returned from the selectiveDeploy API method.
        :type task_token: str
        :return: A dictionary including the overall deployment status and the deployment status of individual entities.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                task_token = "fc093c43-d1a1-4a70-a3a6-511e783a9a73"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    task_status = client.get_deployment_task_status(task_token)
                print(task_status)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return json.loads(self.raw_api.getDeploymentTaskStatus(task_token))

    def deploy_server(self, id: int):
        """
        Deploy the server. When invoking this method, the server is immediately deployed.

        :param id: The object ID of the server to deploy.
        :type id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.deploy_server(<server_id>)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        self.raw_api.deployServer(id)

    def selective_deploy(self, entity_ids: list, properties: Optional[dict] = None) -> str:
        """
        Create a differential deployment task to deploy changes made to specific DNS entities, such as resource records,
        to a managed DNS/DHCP Server.

        .. note::
            The selectiveDeploy API method can be used to deploy DNS resource records that have moved zones.
            The new zone of the resource record must be deployed to the same DNS/DHCP Server as the previous zone
            that the resource record was deployed to. The DNS resource record cannot be deployed if the new zone
            is deployed to a different DNS/DHCP Server.

        :param entity_ids: A list of entity IDs that specify the DNS entities to deploy.
         Currently, only DNS resource records are supported.

         .. note:: Restrictions:

           * Only deploy a maximum of 100 DNS entities per selective deployment API call.
           * Cannot deploy dynamic records, external host records, and resource records which belongs to multiple
             DNS/DHCP Servers.
           * If resource records are being deployed that have moved zones, the new zone of the resource record
             must be deployed to the same DNS/DHCP Server as the previous zone that the resource record was
             deployed to. The resource record cannot be deployed if the new zone is deployed to a
             different DNS/DHCP Server.
        :type entity_ids: list[int]
        :param properties: Contains the following deployment options:

            * scope - a string value. This property defines whether the deployment task includes objects that are
              related to the defined DNS resource records. The scope can be one of the following values:

              * related (default value) - deploys the DNS resource records defined in the entityIds list including
                DNS resource records that are related to those entities. For more information on additional entities
                that are deployed when the related scope is defined, refer to Reference: selective deployment
                related scope.
              * specific - deploys only the DNS resource records that are defined in the entity_ids list.

            * batchMode - an enum value. This property batches selective deployment tasks. The scope can be one of the
              following values:

              * disabled (default value) - disables the batching of selective deployment tasks.
              * batch_by_server - enables the batching of selective deployment tasks.

              .. note:: The batching of selective deployment tasks is dependent on the following conditions:

                * The tasks are from the same server.
                * Each deployment task that is configured for batching must have batchMode set to batch_by_server.
                * The batched deployment contains less than 100 resource records.

            * continueOnFailure - a boolean value. This property specifies the mode of operation on a failed
              resource record. If set to false, deployment stops when a record fails. If set to true,
              deployment continues when a record fails and moves to the next record. The default value is true if
              batchMode is set to batch_by_server, otherwise the default value is false.

            * dynamicRecords - an enum value. This property defines how dynamic records are handled
              with selective deployment tasks. The value can be one of the following:

              * fail (default value) - the selective deployment task fails when a dynamic record is encountered.
              * skip - skips dynamic records by removing them from the list of entity IDs before
                the selective deployment task is performed.

                .. note:: If a selective deployment is performed where all entities are dynamic and
                  the skip option is defined, all records will be removed from the selective deployment task and
                  the deployment fails with the following message: ``Verify input error.: Empty entity id input``

              * makestatic - dynamic records are updated to static records before the selective deployment task
                is performed. This option can be used to convert previously created dynamic records, such as
                records created using the addDeviceInstance method, to static records and selectively deploy
                the changes to the DNS/DHCP Server. This has no effect on related records that are deployed
                using the related scope.

                .. note:: If the makestatic option is defined and the selective deployment task fails for any reason,
                  the updated records are not rolled back and remain static records.

        :type properties: dict
        :return: A token string value of the deployment task.
        :rtype: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_ids = [<entity_1>, <entity_n>]
                properties = {"batchMode": "batch_by_server"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    token = client.selective_deploy(entity_ids, properties)
                print(token)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.selectiveDeploy(properties, entity_ids)

    def quick_deploy(self, entity_id: int, properties: Optional[dict] = None):
        """
        Instantly deploy changes made to DNS resource records since the last full or quick deployment.
        This method only applies to DNS resource records that have been changed and does not deploy any other data.

        :param entity_id: The object ID of the DNS zone or network for which the deployment service is being deployed.
        :type entity_id: int
        :param properties: A dictionary containing the services option. It can also be None.

            * services - the name of the valid service that need to be deployed.
              The only valid service name for quick deployment is **DNS**. Any other service names will throw an error.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {"services": "DNS"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.quick_deploy(<entity_id>, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.quickDeploy(entity_id, properties)

    def replace_server(
        self,
        server_id: int,
        name: str,
        default_interface: str,
        host_name: str,
        password: str,
        upgrade: bool,
        properties: dict,
    ):
        """
        Replace a server.

        :param server_id: The object ID of the server to replace.
        :type server_id: int
        :param name: Name of the server to replace.
        :type name: str
        :param default_interface: Management interface address for the server.
        :type default_interface: str
        :param host_name: The DNS FQDN by which the server is referenced.
        :type host_name: str
        :param password: The server password. For more information on the default server password,
         refer to BlueCat default login credentials.
        :type password: str
        :param upgrade: Flag indicating that server needs to be upgraded or not. True means server needs to be upgraded.
        :type upgrade: bool
        :param properties: A dictionary containing the following options:

            * servicesIPv4Address - IPv4 address used only for services traffic such as DNS, DHCP, DHCPv6 and TFTP.
              If dedicated management is enabled, this option must be specified. If dedicated management is disabled,
              this address must be the same as defaultInterfaceAddress which is management interface address.
            * servicesIPv4Netmask - IPv4 netmask used only for services traffic such as DNS, DHCP, DHCPv6 and TFTP.
              If dedicated management is enabled, this option must be specified. If dedicated management is disabled,
              this netmask address must be the same as the management interface netmask address.
            * servicesIPv6Address - IPv6 address used only for services traffic such as DNS, DHCP, DHCPv6 and TFTP.
              This is optional.
            * servicesIPv6Subnet - IPv6 subnet used only for services traffic such as DNS, DHCP, DHCPv6 and TFTP.
              This is optional.
            * xhaIPv4Address - IPv4 address used for XHA. This is optional.
            * xhaIPv4Netmask - IPv4 netmask used for XHA. This is optional.
            * redundancyScenario - networking redundancy scenarios. The possible values are ACTIVE_BACKUP Failover and
              IEEE_802_3AD Load Balancing.
            * resetServices - allow for replacing the DNS/DHCP Server while maintaining existing configurations
              for DNS, DHCP, and TFTP services. Define this option only if the IPv4 or IPv6 addresses of
              the Services interface have been modified or the configurations needs to be reset for DNS, DHCP, and
              TFTP services on the DNS/DHCP Server. The value is either true or false by default, false.

              .. note:: For DNS/DHCP Servers without multi-port support, the interface-related property options
                will be ignored.

              .. note:: Resetting DNS/DHCP Servers will result in a service outage. This service outage will last until
                services have been deployed to the replacement system. Only reset DNS/DHCP Server services if
                the DNS/DHCP Server are being replaced with a new appliance of a different type or reconfiguring
                the IPv4 or IPv6 addresses of the Services interface on the appliance. BlueCat recommends that
                a maintenance window is scheduled before performing a reset of DNS/DHCP Server services.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_id = <server_id>
                name = "server-name"
                default_interface = <ip_address>
                host_name = <existing_hostname>
                password = <server_password>
                upgrade = "false"
                properties = {"servicesIPv4Address": <ip4_address>, "servicesIPv4Netmask": <ipr_netmask>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.replace_server(server_id, name, default_interface, host_name, password, upgrade, properties)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.replaceServer(
            server_id, name, default_interface, host_name, password, upgrade, properties
        )

    # endregion Servers

    # region Additional IP Addresses

    def get_additional_ip_addresses(
        self, server_id: int, properties: Optional[dict] = None
    ) -> list:
        """
        Get a list of IPv4 addresses and loopback addresses added to the Service interface for DNS services.

        :param server_id: The object ID of the server from which the additional IP addresses is being retrieved.
        :type server_id: int
        :param properties: The supported property is:

            * serviceType - type of service for which a list of IP addresses is being retrieved.
              If serviceType is not provided, all additional IP addresses of the services interface
              will be returned.

        :type properties: dict
        :return: The list of additional IP addresses configured on the server.
        :rtype: list[str]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.constants import AdditionalIPServiceType
                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_id = <server_id>
                properties = {"serviceType": AdditionalIPServiceType.SERVICE}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip_addresses = client.get_additional_ip_addresses(server_id, properties)
                print(ip_addresses)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.getAdditionalIPAddresses(server_id, properties)[:-1].split("|")

    def remove_additional_ip_addresses(
        self, server_id: int, ips: list, properties: Optional[dict] = None
    ):
        """
        Remove additional IPv4 addresses and loopback addresses from the Service interface.

        :param server_id: The object ID of the server from which additional IP addresses is being removed.
        :type server_id: int
        :param ips: The list of IP addresses to remove. The multiple IP addresses are specified  with a separator (|).
            The supported format is [IP,serviceType| IP,serviceType].
        :type ips: list[str]
        :param properties: Object properties. Currently there is no supported properties. Reserved for future use.
        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                server_id = <server_id>
                ips = [
                    "10.0.0.10/32,loopback",
                    "11.0.0.3/24,service"
                ]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.remove_additional_ip_addresses(server_id, ips)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        ips = serialize_joined_values(values=ips, item_sep="|")
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.removeAdditionalIPAddresses(server_id, ips, properties)

    # endregion Additional IP Addresses

    # region DHCP Match Class

    def add_dhcp_match_class(
        self, configuration_id: int, name: str, type: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DHCP match class to Address Manager.

        :param configuration_id: The object ID of the configuration to which the DHCP match class is being added.
        :type configuration_id: int
        :param name: The name of the DHCP match class.
        :type name: str
        :param type: The type of the match criteria.
            This type must be one of the constants listed for DHCP match class criteria.
        :type type: str
        :param properties: Object properties, following properties and values:

            * description - A description of the match class.
            * matchOffset - The Match Offset value for the MatchClass.
              It refers to the point where the match should begin.
            * matchLength - The Match Length value for the MatchClass. It refers to the number of characters to match.
            * customMatchRawString - A raw string that maps directly to a data or boolean expression for
              DHCP_CLASS_CUSTOM_MATCH and DHCP_CLASS_CUSTOM_MATCH_IF constants.

            .. note::

                * matchOffset and matchLength only apply to the following five constants:

                    * DHCP_CLASS_HARDWARE
                    * DHCP_CLASS_CLIENT_ID
                    * DHCP_CLASS_VENDOR_ID
                    * DHCP_CLASS_AGENT_CIRCUIT_ID
                    * DHCP_CLASS_AGENT_REMOTE_ID
                * matchOffset and matchLength must be specify together.

        :type properties: dict
        :return: The object ID of the new DHCP match class.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DHCPMatchClass

                configuration_id = <configuration_id>
                name = "dhcp-match-class-name"
                type = DHCPMatchClass.DHCP_CLASS_VENDOR_ID
                properties = {"matchOffset": 0, "matchLength": 256}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity_id = client.add_dhcp_match_class(configuration_id, name, type, properties)
                print(entity_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPMatchClass(configuration_id, name, type, properties)

    def add_dhcp_sub_class(
        self, match_class_id: int, value: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a DHCP match class value.

        :param match_class_id: The object ID of the match class in which the DHCP match class value is being added.
        :type match_class_id: int
        :param value: The value of the DHCP match value to be matched with the match class.
            The length of the match value must be equal to the length, in bytes, specified in the match class.
        :type value: str
        :param properties: Object properties, a dictionary including the following options:

            * description - a description of the match class.

        :type properties: dict
        :return: The object ID of the new DHCP match class value.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                match_class_id = <match_class_id>
                # The length value must be equal to the length of the match class
                value = <dhcp_match_class_value>
                properties = {"description": "description about sub class"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity_id = client.add_dhcp_sub_class(match_class_id, value, properties)
                print(entity_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addDHCPSubClass(match_class_id, value, properties)

    # endregion DHCP Match Class

    # region IPv4 Blocks

    def add_ip4_block_by_range(
        self,
        entity_id: int,
        start_address: str,
        end_address: str,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a new IPv4 block defined by an address range. The address range must conform to CIDR boundaries.

        :param entity_id: The object ID of the target object's parent object.
        :type entity_id: int
        :param start_address: An IP address defining the lowest address or start of the block.
        :type start_address: str
        :param end_address: An IP address defining the highest address or end of the block.
        :type end_address: str
        :param properties: Object properties.
        :type properties: dict
        :return: The object ID of the new IPv4 block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {"name": <ipv4_block_name>, "inheritDefaultView": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_block_id = client.add_ip4_block_by_range(
                        <configuration_id>, "10.0.0.1", "10.0.0.10", properties
                    )
                print(ip4_block_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4BlockByRange(entity_id, start_address, end_address, properties)

    def add_ip4_block_by_cidr(
        self, entity_id: int, cidr: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a new IPv4 Block using CIDR notation.

        :param entity_id: The object ID of the target object's parent object.
        :type entity_id: int
        :param cidr: The CIDR notation defining the block. For example: 172.0/16
        :type cidr: str
        :param properties: Object properties.
            For more information about the available options, refer to Property Options Reference.
        :type properties: dict
        :return: The object ID of the new IPv4 block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <configuration_id>
                cidr = "172.0/16"
                properties = {"name": "ipv4-block-name", "allowDuplicateHost": "enable"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_block_id = client.add_ip4_block_by_cidr(entity_id, cidr, properties)
                print(ip4_block_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4BlockByCIDR(entity_id, cidr, properties)

    def add_parent_block(self, object_ids: list) -> int:
        """
        Add a parent block. Create an IPv4 or IPv6 block from a list of IPv4 or IPv6 blocks or networks.
        All blocks and networks must have the same parent but it does not need to be contiguous.

        :param object_ids: A list of the object IDs of IPv4 or IPv6 blocks or networks.
        :type object_ids: list[int]
        :return: The object ID of the new IPv4 or IPv6 parent block.
            This method does not create a name for the new block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                object_ids = [<ip4_network1_id>,<ip4_network2_id>]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_block_id = client.add_parent_block(object_ids)
                print(ip4_block_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return self.raw_api.addParentBlock(object_ids)

    def add_parent_block_with_properties(
        self, object_ids: list, properties: Optional[dict] = None
    ) -> int:
        """
        Add a parent block with properties. Create an IPv4 or IPv6 block with a name from a list of IPv4 or IPv6 blocks
        or networks. All blocks and networks must have the same parent but it does not need to be contiguous.

        :param object_ids: A list of the object IDs of IPv4 or IPv6 blocks or networks.
        :type object_ids: list[int]
        :param properties: A dictionary containing the following option:

            * name - the name of the new IPv4 or IPv6 block to be created.

        :type properties: dict
        :return: The object ID of the new IPv4 or IPv6 parent block.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                object_ids = [<ip4_network1_id>,<ip4_network2_id>]
                properties = {"name": "ip4_block_name"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    ip4_block_id = client.add_parent_block_with_properties(object_ids, properties)
                print(ip4_block_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addParentBlockWithProperties(properties, object_ids)

    def merge_selected_blocks_or_networks(
        self, object_id_to_keep: int, object_ids_to_merge: list[int]
    ) -> None:
        """
        Merge specified IPv4 blocks or IPv4 networks into a single IPv4 block or IPv4 network.
        The list of objects to be merged must all be of the same type (for example, all blocks
        or all networks). The objects must all have the same parent and must be contiguous.

        :param object_id_to_keep: The object ID of the IPv4 block or IPv4 network that will retain
            its identity after the merge.
        :type object_id_to_keep: int
        :param object_ids_to_merge: The object IDs of the IPv4 blocks or IPv4 networks to be merged.
        :type object_ids_to_merge: list[int]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                object_ids_to_merge = [<ip4_block1_id>, <ip4_block2_id>, <ip4_block3_id>]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.merge_selected_blocks_or_networks(<ip4_block1_id>, object_ids_to_merge)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.mergeSelectedBlocksOrNetworks(object_id_to_keep, object_ids_to_merge)

    def get_entity_by_cidr(self, parent_id: int, cidr: str, type: str) -> APIEntity:
        """
        Get an IPv4 Network or IPv4 Block object using its CIDR notation.

        :param parent_id: The object ID of the entity's parent object
        :type parent_id: int
        :param cidr: The CIDR notation defining the network or block.
        :type cidr: str
        :param type: The type of the object being returned. This must be one of the constants listed for
            Object types (IP4Block, IP4Network).
        :type type: str
        :return: return: An IPv4 Network or IPv4 Block object.
        :rtype: APIEntity

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import ObjectType

                parent_id = <ip4_block_id>
                cidr = "172.0.0/24"
                type = ObjectType.IP4_NETWORK

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    entity = client.get_entity_by_cidr(parent_id, cidr, type)
                print(entity)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        return APIEntity.from_raw_model(self.raw_api.getEntityByCIDR(parent_id, cidr, type))

    def merge_blocks_with_parent(self, ip4_block_ids: list) -> None:
        """
        Merge specified IPv4 blocks into a single block. The blocks must all have the same parent. If blocks are not
        contiguous, The gap between blocks will be automatically found and made contiguous so they can be merged.
        If the parent of the block is a configuration, they cannot contain networks.

        :param ip4_block_ids: The object IDs of the IPv4 blocks to be merged.
        :type ip4_block_ids: list[int]

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                ip4_block_ids = [<ip4_block1_id>, <ip4_block2_id>]

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.merge_blocks_with_parent(ip4_block_ids)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.mergeBlocksWithParent(ip4_block_ids)

    # endregion IPv4 Blocks

    # region IPv4 Discovery and Reconciliation

    def add_ip4_reconciliation_policy(self, parent_id: int, name: str, properties: dict) -> int:
        """
        Add an IPv4 reconciliation policy.

        :param parent_id: The object ID of the parent object of the policy.
            The IPv4 reconciliation policies can be created at the configuration, IPv4 block, and
            IPv4 network levels.
        :type parent_id: int
        :param name: The name of the IPv4 reconciliation policy.
        :type name: str
        :param properties: Object properties and values listed in ``Reconciliation properties
            and values``.

            .. note:: The hour specified for `schedule` must be in 12-hour clock format.

        :type properties: dict
        :return: The object ID of the new reconciliation policy.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DiscoveryType, SNMPVersion

                parent_id = <configuration_id>
                name = "reconciliation-policy-name"
                properties = {
                    "discoveryType": DiscoveryType.SNMP,
                    "seedRouterAddress": "10.244.140.124",
                    "snmpVersion": SNMPVersion.V1,
                    "snmpPortNumber": 161,
                    "snmpCommunityString": "public",
                    "networkBoundaries": "10.0.0.0/8",
                    "schedule": "09:59AM,01 Nov 2021,ONCE",
                }

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    policy_id = client.add_ip4_reconciliation_policy(parent_id, name, properties)
                print(policy_id)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addIP4ReconciliationPolicy(parent_id, name, properties)

    # endregion IPv4 Discovery and Reconciliation

    # region TFTP

    def add_tftp_file(
        self,
        entity_id: int,
        name: str,
        data: Union[str, IO],
        version: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> int:
        """
        Add a TFTP file.

        :param entity_id: The object ID of the parent object of the TFTP file. The parent can be a TFTP folder or
         TFTP group.
        :type entity_id: int
        :param name: The name of the TFTP file.
        :type name: str
        :param data: The data to be uploaded and distributed to clients by TFTP.
        :type data: IO
        :param version: The version of the file.
        :type version: str
        :param properties: Object properties, including user-defined fields and description properties.
        :type properties: dict
        :return: The object ID of the new TFTP file.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                name = "tftp-file-name"
                version = <file_version>
                properties = {<udf_name>: <udf_value>}

                # Add TFTP file where input data is a string
                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tftp_file_id = client.add_tftp_file(<entity_id>, name, "example data", version, properties)

                # Add TFTP file where input data is an I/O stream
                with Client(<bam_host_url>) as client, open("test.png", "rb") as file:
                    client.login(<username>, <password>)
                    tftp_file_id = client.add_tftp_file(<entity_id>, name, file, version, properties)
                print(tftp_file_id)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTFTPFile(entity_id, name, version, properties, data)

    def add_tftp_group(
        self, configuration_id: int, name: str, properties: Optional[dict] = None
    ) -> int:
        """
        Add a TFTP group.

        :param configuration_id: The object ID of the configuration where the TFTP group is being added.
        :type configuration_id: int
        :param name: The name of the TFTP group.
        :type name: str
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new TFTP group.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                configuration_id = <configuration_id>
                name = "tftp-group-name"
                properties = {"comments": "The new TFTP group"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tftp_group_id = client.add_tftp_group(configuration_id, name, properties)
                print(tftp_group_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTFTPGroup(configuration_id, name, properties)

    def add_tftp_folder(self, entity_id: int, name: str, properties: Optional[dict] = None) -> int:
        """
        Add a TFTP folder.

        :param entity_id: The object ID of the parent object of the TFTP folder. The parent is either a TFTP group
         or another TFTP folder object.
        :type entity_id: int
        :param name: The name of the TFTP folder.
        :type name: str
        :param properties: Object properties, including comments and user-defined fields.
        :type properties: dict
        :return: The object ID of the new TFTP folder.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                entity_id = <tftp_group_id>
                name = "tftp-folder-name"
                properties = {"comments": "The new TFTP folder"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tftp_folder_id = client.add_tftp_folder(entity_id, name, properties)
                print(tftp_folder_id)

        .. versionadded:: 21.8.1
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTFTPFolder(entity_id, name, properties)

    def add_tftp_deployment_role(
        self, tftp_group_id: int, server_id: int, properties: Optional[dict] = None
    ) -> int:
        """
        Add a TFTP deployment role to a specified object.

        :param tftp_group_id: The object ID of the TFTP group to which the TFTP deployment role is
            being added.
        :type tftp_group_id: int
        :param server_id: The object ID of the server interface with which the TFTP deployment role
            associates.
        :type server_id: int
        :param properties: Object properties, including user-defined fields.
        :type properties: dict, optional
        :return: The object ID of the new TFTP deployment role.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    tftp_deployment_role_id = client.add_tftp_deployment_role(
                        <tftp_group_id>, <server_id>
                    )
                print(tftp_deployment_role_id)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return self.raw_api.addTFTPDeploymentRole(tftp_group_id, server_id, properties)

    # endregion TFTP

    # region Database Management

    def establish_trust_relationship(
        self, remote_ip: str, username: str, password: str, properties: Optional[dict] = None
    ) -> None:
        """
        Establish a trust relationship between a maximum of three Address Manager servers.
        This is a prerequisite for configuring replication in Address Manager.

        :param remote_ip: The IP address of the standby server.

            .. note:: The standby server must be reachable from the primary server and must have
                database access from the primary server. To enable database access, refer to the
                Configuring database replication section in the `Address Manager Administration Guide`.

        :type remote_ip: str
        :param username: The username of an API user that logs in to Address Manager.
        :type username: str
        :param password: The password of the specified API user.
        :type password: str
        :param properties: This is reserved for future use.
        :type properties: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                remote_ip = <ip_of_another_bam>
                username = <remote_bam_user>
                password = <remote_bam_password>

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.establish_trust_relationship(remote_ip, username, password)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.establishTrustRelationship(remote_ip, username, password, properties)

    def remove_trust_relationship(self, remote_ip: str, properties: Optional[dict] = None) -> None:
        """
        Remove a remote Address Manager server from the trust relationship.

        :param remote_ip: The IP address of the standby server.

            .. note:: If the standby server is in replication, it must first be removed from
                replication before it can be removed from the trust relationship.

        :type remote_ip: str
        :param properties: This is reserved for future use.
        :type properties: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.remove_trust_relationship(<remote_ip>)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.removeTrustRelationship(remote_ip, properties)

    def get_replication_info(self) -> dict:
        """
        Get Address Manager replication information.

        :return: The Address Manager replication information containing the hostname,
            status of replication, latency, the IP address of the Primary and standby servers,
            and cluster information.
        :rtype: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    status = client.get_replication_info()
                print(status)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        return json.loads(self.raw_api.getReplicationInfo())

    def configure_streaming_replication(
        self,
        standby_server: str,
        compress_replication: bool = False,
        latency_warning_threshold: int = 3600,
        latency_critical_threshold: int = 86400,
        properties: Optional[dict] = None,
    ) -> None:
        """
        Enable database replication on a remote system to automate the setup of replication between
        two or three Address Manager systems.

        .. note:: The Address Manager server that this method runs against becomes the primary
          Address Manager.

        :param standby_server: The IP address of the standby Address Manager.

            .. note:: When adding a standby server, the server cannot be part of
                an existing database replication environment or a removed standby server.
                You can only add a standby server if it is operating as a Standalone server.

        :type standby_server: str
        :param compress_replication: If set to ``True``, compress database replication files.
            The default value is ``False``.

            .. note:: Compressing database replication files is a resource-intensive process
                that might affect system performance. Use caution when performing this action.

        :type compress_replication: bool
        :param latency_warning_threshold: The value to specify the warning threshold latency of replication,
            in seconds (sec). Valid values for the parameter range from 0 to any positive value.
            The default value is ``3600`` seconds.
        :type latency_warning_threshold: int
        :param latency_critical_threshold: The value to specify the critical threshold latency of replication,
            in seconds (sec). Valid values for the parameter range from 0 to any positive value.
            The default value is ``86400`` seconds.
        :type latency_critical_threshold: int
        :param properties: A dictionary containing the following option:

            * secondStandbyServer - Used to add an additional standby server. The server's IP address is required.

        :type properties: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                standby_server = <ip4_address>
                properties = {"secondStandbyServer": <ip4_address>}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.configure_streaming_replication(standby_server, False, 3600, 86400, properties)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.configureStreamingReplication(
            standby_server,
            compress_replication,
            latency_warning_threshold,
            latency_critical_threshold,
            properties,
        )

    def break_replication(self) -> None:
        """
        Break replication and return the primary server to the original stand-alone state.

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.break_replication()

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.breakReplication()

    def failover_replication(self, standby_server: str, properties: dict) -> None:
        """
        Perform a manual replication failover.

        :param standby_server: The IP address of the standby server, which will become the primary
            BAM server once a failover has been performed.
        :type standby_server: str
        :param properties: A dictionary containing the following option:

            * **forceFailover** - A boolean value indicates whether or not a forced failover.

            .. note:: If the latency of the database replication of the server relative to the
                primary server is greater than 0, a forced failover can be performed.

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                standby_server = <ip4_address>
                properties = {"forceFailover": "true"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.failover_replication(standby_server, properties)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.failoverReplication(standby_server, properties)

    # endregion Database Management

    # region Data Collection Probe

    def get_probe_status(self, defined_probe: str) -> int:
        """
        Check the status of the pre-defined SQL queries that have been triggered to collect data.
        The available constants are LEASE_COUNT_PER_DATE and NETWORK_BLOOM.

        :param defined_probe: The SQL query probe object for which the status is being checked.
        :type defined_probe: str
        :return: Integer value between 0 and 3 representing the status of the data collection process.
        :rtype: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DefinedProbe

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    status_code = client.get_probe_status(DefinedProbe.LEASE_COUNT_PER_DATE)
                print(status_code)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        return self.raw_api.getProbeStatus(defined_probe)

    def start_probe(self, defined_probe: str, properties: Optional[dict] = None) -> None:
        """
        Start collecting data from the Address Manager database using pre-defined SQL queries.

        :param defined_probe: Pre-defined SQL queries that will be triggered to collect data.
            The available values are **LEASE_COUNT_PER_DATE** and **NETWORK_BLOOM**.
        :type defined_probe: str
        :param properties: This is reserved for future use.
        :type properties: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DefinedProbe

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.start_probe(DefinedProbe.NETWORK_BLOOM)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.startProbe(defined_probe, properties)

    def get_probe_data(self, defined_probe: str, properties: Optional[dict] = None) -> APIData:
        """
        Get data for the DHCP Heat Map, IP Allocation Overlay, and DNS Deployment Role Overlay.

        :param defined_probe: Pre-defined SQL queries that will be triggered to collect data.
            The available values are ``LEASE_COUNT_PER_DATE`` and ``NETWORK_BLOOM``.
        :type defined_probe: str
        :param properties: This is reserved for future use.
        :type properties: dict, optional
        :return: A dictionary containing data for the DHCP Heat Map, IP Allocation Overlay, or
            DNS Deployment Role Overlay.
        :rtype: APIData

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client
                from utsc.core._vendor.bluecat_libraries.address_manager.constants import DefinedProbe

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    data = client.get_probe_data(DefinedProbe.NETWORK_BLOOM)
                print(data)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        return APIData.from_raw_model(self.raw_api.getProbeData(defined_probe, properties))

    # endregion Data Collection Probe

    # region Migration

    def migrate_file(self, filename: str) -> None:
        """
        Process the specified XML file into Address Manager. The file must reside in the
        /data/migration/incoming directory on the Address Manager server.

        :param filename: The filename of the XML file in the /data/migration/incoming directory.
            Do not include a path in the filename.
        :type filename: str

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                filename = "filename.xml"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.migrate_file(filename)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.migrateFile(filename)

    def is_migration_running(self, filename: Optional[str] = None) -> bool:
        """
        Report whether the migration service is running. The method can be used to determine
        the processing of a specific file. If no filename is specified, the result indicates whether
        any files are being migrated or queued for migration.

        :param filename: The filename of an XML file in directory `/data/migration/incoming` on
            BlueCat Address Manager. Do not include a path in the filename. This defaults to `None`.
        :type filename: str, optional
        :return: A boolean value indicating if the specified file is currently migrating.
            When using the default `None` value of the filename, returns `True` if there are any
            migration files queued for migration or currently migrating.
        :rtype: bool

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                filename = "filename.xml"

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    running = client.is_migration_running(filename)
                print(running)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        return self.raw_api.isMigrationRunning(filename)

    # endregion Migration

    # region Crossover High Availability (xHA)

    def create_xha_pair(
        self,
        configuration_id: int,
        active_server_id: int,
        passive_server_id: int,
        active_server_new_ip4_address: str,
        properties: dict,
    ) -> None:
        """
        Create an xHA pair.

        :param configuration_id: The object ID of the configuration in which the xHA servers are
            located.
        :type configuration_id: int
        :param active_server_id: The object ID of the active DNS/DHCP Server.
        :type active_server_id: int
        :param passive_server_id: The object ID of the passive DNS/DHCP Server.
        :type passive_server_id: int
        :param active_server_new_ip4_address: The new IPv4 address for the active server.

            .. note:: This is the physical interface of the active server used during creation of
                the pair. The original IP address of the active server is assigned to
                the virtual interface.

        :type active_server_new_ip4_address: str
        :param properties: A dictionary containing the following options:

            * **activeServerPassword**: The deployment password for the active server.
            * **passiveServerPassword**: The deployment password for the passive server.

                .. note:: For more information on default server password, refer to BlueCat default
                    login credentials (the user must be authenticated to view this topic).

            * **pingAddress**: An IPv4 address that is accessible to both active and passive servers
              in the xHA pair.
            * **ip6Address**: An optional IPv6 address for the xHA pair.
            * **newManagementAddress**: The new IPv4 address for the Management interface for
              the active server (only for DNS/DHCP Servers with dedicated management enabled).
            * **backboneActiveServerIPv4Address**: The IPv4 address of the xHA interface for
              the active server (eth1).
            * **backboneActiveServerIPv4Netmask**: The IPv4 netmask of the xHA interface for
              the active server (eth1).
            * **backbonePassiveServerIPv4Address**: The IPv4 address of the xHA interface for
              the passive server (eth1).
            * **backbonePassiveServerIPv4Netmask**: The IPv4 netmask of the xHA interface for
              the passive server (eth1).
            * **activeServerIPv4AddressForNAT**: The inside virtual IPv4 address for
              the active server.
            * **passiveServerIPv4AddressForNAT**: The inside virtual IPv4 address for
              the passive server.
            * **activeServerNewIPv4AddressForNAT**: The inside physical IPv4 address for
              the active server.

        :type properties: dict

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                properties = {"activeServerPassword": "bluecat", "passiveServerPassword": "bluecat"}

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.create_xha_pair(
                        <configuration_id>, <active_server_id>, <passive_server_id>,
                        <active_server_new_ip4_address>, properties
                    )

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.createXHAPair(
            configuration_id,
            active_server_id,
            passive_server_id,
            active_server_new_ip4_address,
            properties,
        )

    def edit_xha_pair(
        self, xha_server_id: int, name: str, properties: Optional[dict] = None
    ) -> None:
        """
        Update the xHA pair created.

        :param xha_server_id: The object ID of the xHA server.
        :type xha_server_id: int
        :param name: The name of the xHA server being updated.
        :type name: str
        :param properties: A dictionary containing the following options listed in ``editing xHA
            option list``.
        :type properties: dict, optional

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.edit_xha_pair(<xha_server_id>, <name>)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        properties = serialize_joined_key_value_pairs(properties)
        self.raw_api.editXHAPair(xha_server_id, name, properties)

    def failover_xha(self, xha_server_id: int) -> None:
        """
        Perform a manual xHA failover.

        :param xha_server_id: The object ID of the xHA server.
        :type xha_server_id: int

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.failover_xha(<xha_server_id>)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.failoverXHA(xha_server_id)

    def break_xha_pair(self, xha_server_id: int, break_in_proteus_only: bool = False) -> None:
        """
        Break an xHA pair and return each server to its original stand-alone state.

        :param xha_server_id: The object ID of the xHA server.
        :type xha_server_id: int
        :param break_in_proteus_only: A boolean value, to determine whether or not
            the xHA pair breaks in the Address Manager interface only. This argument breaks
            the xHA pair in Address Manager, even if the xHA settings are not removed on
            the actual servers.
        :type break_in_proteus_only: bool

        Example:

            .. code-block:: python

                from utsc.core._vendor.bluecat_libraries.address_manager.api import Client

                with Client(<bam_host_url>) as client:
                    client.login(<username>, <password>)
                    client.break_xha_pair(<xha_server_id>, False)

        .. versionadded:: 21.11.2
        """
        self._require_auth()
        self.raw_api.breakXHAPair(xha_server_id, break_in_proteus_only)

    # endregion Crossover High Availability (xHA)
