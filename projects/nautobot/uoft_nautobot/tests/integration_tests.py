import pytest
import socket
from subprocess import Popen, PIPE
import requests
import time
from uoft_core import debug_cache
import openpyxl

@pytest.fixture(scope="session", autouse=True)
def nautobot_running():
    """Check if Nautobot is running."""
    p = None
    try:
        socket.create_connection(("localhost", 8000))
    except OSError:
        # start nautobot
        p = Popen(["invoke", "nautobot.start"], stdout=PIPE, stderr=PIPE, text=True)
    
    # wait 30s for nautobot to start
    for _ in range(7):
        try:
            requests.get("http://localhost:8000/health")
            break
        except Exception:
            time.sleep(5)
    else:
        if p:
            stdout, stderr = p.communicate(timeout=1)
            raise Exception(f"Nautobot did not start in time. stout: {stdout}, stderr: {stderr}")
        else:
            raise Exception("Nautobot was started externally, but doesn't seem to be running correctly (http://localhost:8000/health not ok?)")

    yield

    # stop nautobot
    if p:
        p.terminate()


@debug_cache
def get_all_interfaces(device=None):
    """Get all interfaces from Nautobot."""
    from uoft_core import shell
    t = shell("pass nautobot-secrets")
    for l in t.splitlines():
        if "MY_API_TOKEN=" in l:
            password = l.split("=")[1].split("'")[1]
            break
    else:
        raise Exception("Could not find password in nautobot-secrets")
    intfs = []
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Token {password}"})
    device_query = f"&device={device}" if device else ""
    r = ses.get(f"http://localhost:8000/api/dcim/interfaces/?limit=1000{device_query}")
    r.raise_for_status()
    r = r.json()
    intfs.extend(r['results'])
    while r['next']:
        r = ses.get(r['next'])
        r.raise_for_status()
        r = r.json()
        intfs.extend(r['results'])

    for intf in intfs:
        intf['device'] = intf['device']['name']
        intf['type'] = intf['type']['value']
        intf['parent_interface'] = intf['parent_interface']['name'] if intf['parent_interface'] else None
        intf['bridge'] = intf['bridge']['name'] if intf['bridge'] else None
        intf['lag'] = intf['lag']['name'] if intf['lag'] else None
        intf['mode'] = intf['mode']['value'] if intf['mode'] else None
        intf['untagged_vlan'] = intf['untagged_vlan']['vid'] if intf['untagged_vlan'] else None
        intf['tagged_vlans'] = [v['vid'] for v in intf['tagged_vlans']]
        intf['cable'] = intf['cable']['id'] if intf['cable'] else None
        intf['tags'] = [t['slug'] for t in intf['tags']]
    return intfs


def test_something(nautobot_running):
    intfs = get_all_interfaces('a1-p50c')
    wb = openpyxl.Workbook()
    wb.create_sheet("Interfaces")
    ws = wb["Interfaces"]
    ws.append(tuple(intfs[0].keys()))
    for intf in intfs:
        for k,v in intf.items():
            if isinstance(v, list):
                intf[k] = "\n".join(v)
            if isinstance(v, dict):
                intf[k] = "\n".join([f"{k}: {v}" for k,v in v.items()])
        ws.append(tuple(intf.values()))
    wb.save("test.xlsx")
    assert True
