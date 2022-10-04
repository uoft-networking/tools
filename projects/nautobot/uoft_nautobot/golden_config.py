from box import Box
from netaddr import IPNetwork

def annotate_intf_ip(intf):
    intf.ip = Box()
    intf.ip.v4 = []
    intf.ip.v6 = []
    for addr in intf.ip_addresses:
        addr = IPNetwork(addr.address)
        if addr.version == 4:
            intf.ip.v4.append(addr)
        else:
            intf.ip.v6.append(addr)
    return intf

def annotate_intf_type(intf):
    if intf.mgmt_only:
        intf.type = "management"
    elif intf.enabled is False:
        intf.type = "disabled"
    elif intf.name.startswith("Port-channel"):
        intf.type = "port-channel"
    elif intf.lag:
        intf.type = "port-channel-member"
    elif intf.label and "uplink" in intf.label.lower():
        intf.type = "uplink"
    elif "tagged" in intf.vlan_mode.lower():
        intf.type = "trunk"
    else:
        intf.type = "other"
    return intf

def process_interfaces(d):
    
    def yield_interfaces():
        yield from d.interfaces
        for db in d.devicebays:
            yield from db.installed_device.interfaces
    
    def sort_interfaces(intfs):
        d = {
            "Loopback" : [],
            "Port-channel" : [],
            "GigabitEthernet" : [],
            "TenGigabitEthernet1" : [],
            "FortyGigabitEthernet1" : [],
            "other" : [],
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
        yield from res

    def annotate_interfaces(intfs):
        for intf in intfs:
            int = annotate_intf_ip(intf)
            intf["uplink"] = "uplink" in intf.label.lower()
            yield intf
    
    d.all_interfaces = list(annotate_interfaces(sort_interfaces(yield_interfaces())))
    return d

def transposer(data):
    d = Box(data)

    d = process_interfaces(d)

    return d