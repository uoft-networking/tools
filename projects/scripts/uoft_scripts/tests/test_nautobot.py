from uoft_scripts import nautobot
from pathlib import Path
import socket
from subprocess import Popen, PIPE
import time

import pytest
from pytest_mock import MockerFixture
import requests

from uoft_core import debug_cache


@pytest.fixture(scope="session")
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
            raise Exception(
                "Nautobot was started externally, but doesn't seem to be running correctly \
                    (http://localhost:8000/health not ok?)"
            )

    yield

    # stop nautobot
    if p:
        p.terminate()


@debug_cache
def get_all_interfaces(device=None):
    """Get all interfaces from Nautobot."""
    from uoft_core import shell

    stdout = shell("pass nautobot-secrets")
    for line in stdout.splitlines():
        if "MY_API_TOKEN=" in line:
            password = line.split("=")[1].split("'")[1]
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
    intfs.extend(r["results"])
    while r["next"]:
        r = ses.get(r["next"])
        r.raise_for_status()
        r = r.json()
        intfs.extend(r["results"])

    for intf in intfs:
        intf["device"] = intf["device"]["name"]
        intf["type"] = intf["type"]["value"]
        intf["parent_interface"] = intf["parent_interface"]["name"] if intf["parent_interface"] else None
        intf["bridge"] = intf["bridge"]["name"] if intf["bridge"] else None
        intf["lag"] = intf["lag"]["name"] if intf["lag"] else None
        intf["mode"] = intf["mode"]["value"] if intf["mode"] else None
        intf["untagged_vlan"] = intf["untagged_vlan"]["vid"] if intf["untagged_vlan"] else None
        intf["tagged_vlans"] = [v["vid"] for v in intf["tagged_vlans"]]
        intf["cable"] = intf["cable"]["id"] if intf["cable"] else None
        intf["tags"] = [t["name"] for t in intf["tags"]]
    return intfs


@pytest.fixture()
def mock_sync_data(mocker: MockerFixture):
    # TODO: rewrite this test to use the new _sync.Target classes
    raise NotImplementedError()
    # import pickle
    # fixtures = Path(__file__).parent / "fixtures/_private"
    # fixtures.mkdir(exist_ok=True, parents=True)
    # from uoft_scripts import _sync

    # # nautobot
    # nautobot_orig = nautobot.NautobotManager.load_data_raw
    # nautobot_data_file = fixtures / "nautobot_raw.pkl"

    # def nautobot_new(self):
    #     if nautobot_data_file.exists():
    #         with open(nautobot_data_file, "rb") as f:
    #             return pickle.load(f)
    #     else:
    #         data = nautobot_orig(self)
    #         with open(nautobot_data_file, "wb") as f:
    #             pickle.dump(data, f)
    #         return data

    # mocker.patch(
    #     "uoft_scripts.nautobot.NautobotManager.load_data_raw", new=nautobot_new
    # )

    # # bluecat
    # bluecat_orig = nautobot.BluecatManager.load_data_raw
    # bluecat_data_file = fixtures / "bluecat_raw.pkl"

    # def new_method(self):
    #     if bluecat_data_file.exists():
    #         with open(bluecat_data_file, "rb") as f:
    #             return pickle.load(f)
    #     else:
    #         data = bluecat_orig(self)
    #         with open(bluecat_data_file, "wb") as f:
    #             pickle.dump(data, f)
    #         return data

    # mocker.patch("uoft_scripts.nautobot.BluecatManager.load_data_raw", new=new_method)


# TODO: rewrite these tests to use the new _sync.Target classes
# def test_bluecat_manager():
#     bc = nautobot.BluecatManager()
#     bc.load_data()
#     assert bc.syncdata


# def test_nautobot_manager():
#     nb = nautobot.NautobotManager(dev=True)
#     nb.load_data()
#     assert nb.syncdata


def test_multithreaded_sync(nautobot_running):
    nautobot.sync_from_bluecat()
    print()


def test_autocomplete_hostnames(mocker):
    all_hostanames = nautobot._autocomplete_hostnames(ctx=mocker.Mock(), partial="")
    access_switches = nautobot._autocomplete_hostnames(ctx=mocker.Mock(), partial="a1-")
    assert isinstance(all_hostanames, list)
    assert isinstance(access_switches, list)
    assert len(all_hostanames) > len(access_switches)


def test_show_golden_config_data():
    nautobot.show_golden_config_data("d1-ia")


def test_trigger_golden_config_intended():
    nautobot.trigger_golden_config_intended("d1-ia")


def test_golden_config_templates():
    # TODO: fix this terrible hack, should not bake specific paths into the code
    templates_dir = Path(
        "~/uoft-tools/projects/nautobot/uoft_nautobot/tests/fixtures/_private/.gitlab_repo"
    ).expanduser()
    nautobot.push_changes_to_nautobot(templates_dir)
    nautobot.test_golden_config_templates("d1-ia", templates_dir=templates_dir)
