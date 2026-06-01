from typing import List, Optional, Union, TypedDict


class Device(TypedDict):
    device_id: int
    inserted: Optional[str]
    hostname: str
    sysName: str
    display: None
    ip: str
    overwrite_ip: Optional[str]
    community: Optional[str]
    authlevel: Optional[str]
    authname: Optional[str]
    authpass: Optional[str]
    authalgo: Optional[str]
    cryptopass: Optional[str]
    cryptoalgo: Optional[str]
    snmpver: str
    port: int
    transport: str
    timeout: None
    retries: None
    snmp_disable: int
    bgpLocalAs: Optional[int]
    sysObjectID: Optional[str]
    sysDescr: Optional[str]
    sysContact: Optional[str]
    version: Optional[str]
    hardware: Optional[str]
    features: Optional[str]
    location_id: Optional[int]
    os: str
    status: int
    status_reason: str
    ignore: int
    disabled: int
    uptime: Optional[int]
    agent_uptime: int
    last_polled: Optional[str]
    last_poll_attempted: Optional[str]
    last_polled_timetaken: Union[None, float, int]
    last_discovered_timetaken: Union[None, float, int]
    last_discovered: Optional[str]
    last_ping: Optional[str]
    last_ping_timetaken: Union[None, float, int]
    purpose: Optional[str]
    type: str
    serial: Optional[str]
    icon: Optional[str]
    poller_group: int
    override_sysLocation: int
    notes: None
    port_association_mode: int
    max_depth: int
    disable_notify: int
    dependency_parent_id: Optional[str]
    dependency_parent_hostname: Optional[str]
    location: Optional[str]
    lat: Optional[float]
    lng: Optional[float]


class Devices(TypedDict):
    status: str
    devices: List[Device]
    count: int


class Port(TypedDict):
    port_id: int
    device_id: int
    port_descr_type: None
    port_descr_descr: None
    port_descr_circuit: None
    port_descr_speed: None
    port_descr_notes: None
    ifDescr: str
    ifName: str
    portName: None
    ifIndex: int
    ifSpeed: int
    ifSpeed_prev: None
    ifConnectorPresent: str
    ifPromiscuousMode: str
    ifOperStatus: str
    ifOperStatus_prev: str
    ifAdminStatus: str
    ifAdminStatus_prev: str
    ifDuplex: None
    ifMtu: int
    ifType: str
    ifAlias: str
    ifPhysAddress: None
    ifHardType: None
    ifLastChange: int
    ifVlan: str
    ifTrunk: str
    ifVrf: int
    counter_in: None
    counter_out: None
    ignore: int
    disabled: int
    detailed: int
    deleted: int
    pagpOperationMode: None
    pagpPortState: None
    pagpPartnerDeviceId: None
    pagpPartnerLearnMethod: None
    pagpPartnerIfIndex: None
    pagpPartnerGroupIfIndex: None
    pagpPartnerDeviceName: None
    pagpEthcOperationMode: None
    pagpDeviceId: None
    pagpGroupIfIndex: None
    ifInUcastPkts: int
    ifInUcastPkts_prev: int
    ifInUcastPkts_delta: int
    ifInUcastPkts_rate: int
    ifOutUcastPkts: int
    ifOutUcastPkts_prev: int
    ifOutUcastPkts_delta: int
    ifOutUcastPkts_rate: int
    ifInErrors: int
    ifInErrors_prev: int
    ifInErrors_delta: int
    ifInErrors_rate: int
    ifOutErrors: int
    ifOutErrors_prev: int
    ifOutErrors_delta: int
    ifOutErrors_rate: int
    ifInOctets: int
    ifInOctets_prev: int
    ifInOctets_delta: int
    ifInOctets_rate: int
    ifOutOctets: int
    ifOutOctets_prev: int
    ifOutOctets_delta: int
    ifOutOctets_rate: int
    poll_time: int
    poll_prev: int
    poll_period: int


class Ports(TypedDict):
    status: str
    ports: List[Port]
    count: int


class PortIP(TypedDict):
    ipv4_address_id: int
    ipv4_address: str
    ipv4_prefixlen: int
    ipv4_network_id: str
    port_id: int
    context_name: str


class PortIPs(TypedDict):
    status: str
    addresses: List[PortIP]
    count: int


class DynamicGroupRule(TypedDict):
    id: str
    field: str
    type: str
    input: str
    operator: str
    value: str


class DynamicGroupRules(TypedDict):
    condition: str
    rules: List[DynamicGroupRule]
    valid: bool
    joins: Union[List, List[List[str]]]


class DeviceGroup(TypedDict):
    id: int
    name: str
    desc: str
    type: str
    rules: DynamicGroupRules
    pattern: Optional[str]


class DeviceGroups(TypedDict):
    status: str
    groups: List[DeviceGroup]
    message: str
    count: int

Component = TypedDict("Component", {
    "UID": str,
    "sp-id": str, # key not always present
    "sp-obj": str, # key not always present
    "qos-type": str, # key not always present
    "parent": str, # key not always present
    "direction": str, # key not always present
    "ifindex": str, # key not always present
    "map-type": str, # key not always present
    "match": str, # key not always present
    "type": str,
    "label": str,
    "status": int,
    "ignore": int,
    "disabled": int,
    "error": None,
    "peer": str, # key not always present
    "port": str, # key not always present
    "stratum": str, # key not always present
    "peerref": str, # key not always present
}, total=False)

class Components(TypedDict):
    status: str
    components: dict[int, Component]
    count: int

class Vlan(TypedDict):
    vlan_id: int
    device_id: int
    vlan_vlan: int
    vlan_domain: int
    vlan_name: str
    vlan_type: Optional[str]
    vlan_mtu: None

class Vlans(TypedDict):
    status: str
    vlans: List[Vlan]
    count: int

class Link(TypedDict):
    id: int
    local_port_id: int
    local_device_id: int
    remote_port_id: Optional[int]
    active: int
    protocol: str
    remote_hostname: str
    remote_device_id: int
    remote_port: str
    remote_platform: Optional[str]
    remote_version: str

class Links(TypedDict):
    status: str
    links: List[Link]
    count: int
