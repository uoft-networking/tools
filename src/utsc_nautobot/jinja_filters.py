from django_jinja import library

from netaddr import IPNetwork


@library.filter
def analyze_obj(obj):
    return obj


@library.filter
def convert_to_IS_id(ipv4: str):
    "take an ip address str and create an ISIS network ID out of it"
    a, b, _, c = ipv4.split(".")
    return f"49.0000.{a:04}.{b:04}.{c:0>4}.00"


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
