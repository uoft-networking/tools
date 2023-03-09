from box import Box
from uoft_core.types import IPNetwork, IPAddress
from pydantic import BaseModel, Field
from typing import Literal
from django.http import HttpRequest
from nautobot_golden_config.models import GoldenConfig
from django_jinja.backend import Jinja2
from jinja2 import Environment, StrictUndefined
from . import Settings


class Building(BaseModel):
    name: str
    code: str

    @classmethod
    def from_nautobot(cls, site: Box):
        res = cls(
            name=site.name,
            code=site.slug.upper(),
        )

        return res


class Room(BaseModel):
    name: str
    description: str
    building: Building

    @classmethod
    def from_nautobot(cls, location: Box):
        res = cls(
            name=location.name,
            description=location.description,
            building=Building.from_nautobot(location.site),
        )

        return res


class Interface(BaseModel):
    name: str
    type: Literal[
        "management",
        "disabled",
        "port-channel",
        "port-channel-member",
        "uplink",
        "other",
    ]
    label: str | None
    ip_v4: IPNetwork | None
    ip_v6: IPNetwork | None
    is_trunk: bool = False
    native_vlan: int = 666
    port_channel: int | None  # only used for port-channel members

    @classmethod
    def from_nautobot(cls, intf: Box):
        addresses = [IPNetwork(addr.address) for addr in intf.ip_addresses]

        def infer_type():
            if intf.mgmt_only:
                return "management"
            elif intf.enabled is False:
                return "disabled"
            elif intf.name.startswith("Port-channel"):
                return "port-channel"
            elif intf.lag:
                return "port-channel-member"
            elif intf.label and "uplink" in intf.label.lower():
                return "uplink"
            else:
                return "other"

        def ip_v4():
            for addr in addresses:
                if addr.version == 4:
                    return addr  # return the first addr in the list
            return None

        def ip_v6():
            for addr in addresses:
                if addr.version == 6:
                    return addr
            return None

        def is_trunk():
            if intf.vlan_mode and "tagged" in intf.vlan_mode.lower():
                return True
            return False

        def port_channel():
            if intf.lag:
                return int(intf.lag.name.replace("Port-channel", ""))
            return None

        res = cls(
            name=intf.name,
            type=infer_type(),
            label=intf.label,
            ip_v4=ip_v4(),
            ip_v6=ip_v6(),
            is_trunk=is_trunk(),
            native_vlan=intf.untagged_vlan.vid if intf.untagged_vlan else 666,
            port_channel=port_channel(),
        )
        return res


class VLAN(BaseModel):
    name: str
    vid: int
    ip_v4: IPNetwork | None
    ip_v6: IPNetwork | None

    @classmethod
    def from_nautobot(cls, vlan: Box):
        def ip_v4():
            if vlan.ipv4:
                return IPNetwork(vlan.ipv4[0].prefix)
            return None

        def ip_v6():
            if vlan.ipv6:
                return IPNetwork(vlan.ipv6[0].prefix)
            return None

        res = cls(
            name=vlan.name,
            vid=vlan.vid,
            ip_v4=ip_v4(),
            ip_v6=ip_v6(),
        )
        return res


class DistributionSwitch(BaseModel):
    hostname: str
    mgmt_ip_v4: IPAddress
    mgmt_ip_v6: IPAddress
    interfaces: list[Interface]
    vlans: list[VLAN]
    tags: set[str] = Field(default_factory=set)
    provisioning: bool = False
    room: Room

    @classmethod
    def from_nautobot(cls, switch: Box):
        def interfaces():
            res = []
            for intf in switch.interfaces:
                res.append(Interface.from_nautobot(intf))
            return sort_interfaces(res)

        def vlans():
            assert (
                len(switch.site.vlan_groups) > 0
            ), "No VLAN group found for site. All dist switches must be in a site with a VLAN group."
            assert (
                len(switch.site.vlan_groups) < 2
            ), "Only one VLAN group per site is supported"
            res = [
                VLAN.from_nautobot(vlan) for vlan in switch.site.vlan_groups[0].vlans
            ]
            return sorted(res, key=lambda x: x.vid)

        def provisioning():
            if switch.status.name == "Planned":
                return True
            return False

        if not isinstance(switch, Box):
            switch = Box(switch)

        return cls(
            hostname=switch.hostname,
            mgmt_ip_v4=IPAddress(switch.primary_ip4.address),
            mgmt_ip_v6=IPAddress(switch.primary_ip6.address),
            interfaces=interfaces(),
            vlans=vlans(),
            tags=set(switch.tags),
            provisioning=provisioning(),
            room=Room.from_nautobot(switch.location),
        )


def sort_interfaces(intfs):
    d = {
        "Loopback": [],
        "Port-channel": [],
        "GigabitEthernet": [],
        "TenGigabitEthernet1": [],
        "FortyGigabitEthernet1": [],
        "other": [],
    }
    for i in intfs:
        for k in d:
            if i.name.startswith(k):
                d[k].append(i)
                break
        else:
            d["other"].append(i)
    res = []
    for l in d.values():
        res.extend(l)
    return res


def transposer(data):
    data = dict(DistributionSwitch.from_nautobot(data))
    return data


def transposer_debug(data):
    data = dict(DistributionSwitch.from_nautobot(data))
    return data


def inject_secrets(
    intended_config: str, configs: GoldenConfig, request: HttpRequest
) -> str:
    """Takes a rendered IntendedConfig, treats it as a Jinja template, and injects secrets into it."""
    if not intended_config:
        return ""

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined

    s = Settings.from_cache()
    secrets = dict(
        enable_hash=encrypt_type9(s.ssh.enable_secret.get_secret_value()),
        admin_hash=encrypt_type9(s.ssh.admin.password.get_secret_value()),
        netdisco_snmp_pw=s.ssh.other["snmp_netdisco"].get_secret_value(),
    )

    template = jinja_env.from_string(intended_config)
    return template.render(**secrets)


# temporary code for inject_secrets post-processor
# This stuff is in the process of being upstreamed to nautobot
import base64
from hashlib import scrypt
import string
import secrets

ALPHABET = string.ascii_letters + string.digits
ENCRYPT_TYPE9_ENCODING_CHARS = "".join(
    ("./", string.digits, string.ascii_uppercase, string.ascii_lowercase)
)
BASE64_ENCODING_CHARS = "".join(
    (string.ascii_uppercase, string.ascii_lowercase, string.digits, "+/")
)

def type9_encode(data: bytes) -> str:
    encoding_translation_table = str.maketrans(
        BASE64_ENCODING_CHARS,
        ENCRYPT_TYPE9_ENCODING_CHARS,
    )
    res = base64.b64encode(data).decode().translate(encoding_translation_table)

    # and strip off the trailing '='
    res = res[:-1]
    return res

def type9_decode(data: str) -> bytes:
    encoding_translation_table = str.maketrans(
        ENCRYPT_TYPE9_ENCODING_CHARS,
        BASE64_ENCODING_CHARS,
    )
    # add back the trailing '='
    data += "=="
    res = data.translate(encoding_translation_table)
    res = base64.b64decode(res)
    return res

def encrypt_type9(unencrypted_password: str, salt: str | None = None) -> str:
    """Given an unencrypted password of Cisco Type 9 password, encypt it.

    Args:
        unencrypted_password: A password that has not been encrypted, and will be compared against.
        salt: a 14-character string that can be set by the operator. Defaults to random generated one.

    Returns:
        The encrypted password.

    Examples:
        >>> from netutils.password import encrypt_type9
        >>> encrypt_type7("123456")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
        >>> encrypt_type7("123456", "cvWdfQlRRDKq/U")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
    """

    if salt:
        if len(salt) != 14:
            raise ValueError("Salt must be 14 characters long.")
    else:
        # salt must always be a 14-byte-long printable string, often includes symbols
        salt = "".join(
            secrets.choice(ENCRYPT_TYPE9_ENCODING_CHARS) for _ in range(14)
        )

    key = scrypt(
        unencrypted_password.encode(), salt=salt.encode(), n=2**14, r=1, p=1, dklen=32
    )

    # Cisco type 9 uses a different base64 encoding than the standard one, so we need to translate from
    # the standard one to the Cisco one.
    hash = type9_encode(key)

    return f"$9${salt}${hash}"


def _debug():
    pass
