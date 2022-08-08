from nautobot.ipam.models import VLAN
from nautobot.dcim.models import Device
from nautobot.dcim.models.device_components import Interface
from django_jinja import library

from netaddr import IPNetwork
from box import Box


@library.filter
def interfaces(data: Device):
    interfaces = list(data.interfaces.all())
    for module in data.devicebays.all():
        if dev := module.installed_device:
            interfaces.extend(dev.interfaces.all())
    return interfaces


@library.filter
def vlans(data: Device):
    for vlan in data.site.vlan_groups.first().vlans.all():
        if vlan.vid != 666:
            yield vlan


@library.filter
def uplinks(interfaces):
    return list(filter(lambda i: "uplink" in i.label.lower(), interfaces))


@library.filter
def ip_info(intf: Interface):
    res = Box()
    res.v4 = []
    res.v6 = []
    for addr in intf.ip_addresses.all():
        if addr.family == 4:
            res.v4.append(addr)
        else:
            res.v6.append(addr)
    return res


@library.filter
def allowed_vlans(native_vlan: int):
    match native_vlan:
        case 1:
            return "2-4094"
        case 2:
            return "3-4094"
        case 4093:
            return "2-4092,4094"
        case 4094:
            return "2-4093"
        case _:
            return f"2-{native_vlan-1},{native_vlan+1}-4094"


@library.filter
def vlan_ip_info(vlan: VLAN):
    res = Box(dict(v4=None, v6=None))
    for pfx in vlan.prefixes.all():
        if pfx.family == 4:
            res.v4 = IPNetwork(pfx.cidr_str)
        else:
            res.v6 = IPNetwork(pfx.cidr_str)
    return res


@library.filter
def analyze_obj(obj):
    return obj


@library.filter
def convert_to_IS_id(ipv4: str):
    "take an ip address str and create an ISIS network ID out of it"
    a, b, _, c = ipv4.split(".")
    return f"49.0000.{a:04}.{b:04}.{c:0>4}.00"


def _sla_object(num, s_ip, s_name, t_ip, t_name):
    res = Box(dict(source={}, target={}))
    res.source.ip = s_ip
    res.source.name = s_name
    res.target.ip = t_ip
    res.target.name = t_name
    res.num = num
    return res


@library.filter
def sla_info(data: Device):
    count = 1
    for vlan in vlans(data):
        ip = vlan_ip_info(vlan)
        if ip.v4:
            if vlan.vid == 100:
                # UTSG SLA
                yield _sla_object(
                    count,
                    ip.v4[1],
                    vlan.name,
                    "128.100.100.123",
                    "UTSG",
                )
                count += 1

            if ip.v4.is_unicast() and not ip.v4.is_private():
                # GOOGLEV4 SLA
                yield _sla_object(
                    count,
                    ip.v4[1],
                    vlan.name,
                    "8.8.8.8",
                    "GOOGLEV4",
                )
                count += 1
        if ip.v6:
            yield _sla_object(
                count,
                ip.v6[1],
                vlan.name,
                "2001:4860:4860::8888",
                "GOOGLEV6",
            )
            count += 1


@library.filter
def ip_sla_data(vlan_list: list[dict]):
    """
    Take a list of ip network prefixes as CIDR strings,
    and filter out all prefixes which are not publicly routable
    """

    def is_public(net):
        return net.is_unicast() and not net.is_private()

    def slas():
        for vlan in vlan_list:
            for family in ("ipv4", "ipv6"):
                if not vlan[family]:
                    continue

                pfx = vlan[family][0]["prefix"]
                net = IPNetwork(pfx)
                if net.version == 4:
                    target = "8.8.8.8"
                    target_name = "GOOGLEV4"
                else:
                    target = "2001:4860:4860::8888"
                    target_name = "GOOGLEV6"
                if is_public(net):
                    yield dict(
                        target=target,
                        source=net[1],
                        target_name=target_name,
                        source_name=vlan["name"],
                    )
                    if not (vlan["vid"] == 100 and net.version == 4):
                        continue
                    target = "128.100.100.123"
                    target_name = "UTSGV4"
                    yield dict(
                        target=target,
                        source=net[1],
                        target_name=target_name,
                        source_name=vlan["name"],
                    )

    return list(slas())
