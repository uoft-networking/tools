from .. import Settings
from ..api import API
from uoft_core.api import RESTAPIError
from uoft_core.types import IPAddress

from typing import Any, Literal

import pytest


@pytest.fixture()
def bluecat_test_data_cleared():
    """Clear all test prefixes (prefixes inside the IPv4 and IPv6 documentation ranges)
    and all records from the test zone (test.netmgmt.utsc.utoronto.ca) from the Bluecat server
    """
    from requests import Session

    s = Settings.from_cache()

    sess = Session()
    url = f"{s.url}/api/v2"
    tok_data = sess.post(f"{url}/sessions", json={"username": s.username, "password": s.password}).json()
    # tok_data contains an apiToken field
    # you would think that the api token would be a valid Bearer token, but it's not
    # using it as such produces a 401 error
    # thanks bluecat!
    # token = tok_data['apiToken']
    # tok_data also contains a basicAuthenticationCredentials field
    # which is a base64 encoded string of the form "username:token"
    credentials = tok_data["basicAuthenticationCredentials"]
    sess.headers.update(
        {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/hal+json",
            "x-bcn-change-control-comment": "Automatically deleting test fixtures from previous test run",
        }
    )

    for addr, prefixlen in [("192.0.2.0", 24), ("2001:DB8:", 32)]:
        # this ugly chunk of code will generate GET requests like:
        # GET /api/v2/networks?filter=range:startsWith("192.0.2.0") and range:le("/24")
        # GET /api/v2/blocks?filter=range:startsWith("192.0.2.0") and range:lt("/24")
        # GET /api/v2/networks?filter=range:startsWith("2001:DB8:") and range:le("/32")
        # GET /api/v2/blocks?filter=range:startsWith("2001:DB8:") and range:lt("/32")
        for endpoint in ["networks", "blocks"]:
            # we want to delete all blocks and networks inside of our target prefixes
            # for blocks we use the "lt"(less than) operator, to find all blocks within the prefix
            # not including the prefix itself, and for networks we use the "le"(less than or equal to) operator
            # to find all networks within the prefix including any that are the size of the prefix itself
            operator = "le" if endpoint == "networks" else "lt"
            for res in sess.get(
                f'{url}/{endpoint}?filter=range:startsWith("{addr}") and range:{operator}("/{prefixlen}")',
            ).json()["data"]:
                print(f"deleting {res['id']}: {res['range']}")
                r = sess.delete(
                    f"{url}/{endpoint}/{res['id']}",
                )
                if r.status_code != 204:
                    raise Exception(r.json())

    test_zone = sess.get(
        f"{url}/zones",
        params=dict(
            filter='absoluteName:"test.netmgmt.utsc.utoronto.ca"',
            fields="embed(resourceRecords)",
        ),
    ).json()["data"][0]
    for rr in test_zone["_embedded"]["resourceRecords"]:
        print(f"deleting {rr['id']}: {rr['absoluteName']} {rr['type']}")
        r = sess.delete(
            f"{url}/resourceRecords/{rr['id']}",
        )
        if r.status_code != 204:
            raise Exception(r.json())


@pytest.fixture(scope="module")
def api_instance():
    s = Settings.from_cache()
    api = API(s.url, s.username, s.password.get_secret_value())
    with api as s:
        yield s


def test_get(bluecat_test_data_cleared, api_instance):
    s = api_instance
    blocks = s.get("/blocks")
    assert blocks.status_code == 200
    blocks = blocks.json()
    assert "data" in blocks
    assert len(blocks["data"]) > 0


def test_get_all():
    with Settings.from_cache().get_api_connection() as api:
        addrs = api.get_all("/addresses", params=dict(filter="state:in('GATEWAY', 'STATIC', 'DHCP_RESERVED')"))
        assert len(addrs) > 0
        assert all("id" in addr for addr in addrs)
        assert all("type" in addr for addr in addrs)
        assert all("name" in addr for addr in addrs)


def _create_network(s: API, parent_block_id: int, addr: str, pfx_len: int, ver: str):
    if ver == "IPv4":
        target_range = f"{addr}/{pfx_len+2}"
    else:
        # Bluecat requires that IPv6 networks have a prefix length minimum of 64
        target_range = f"{addr}/{max(pfx_len+2, 64)}"
    network = s.create_network(
        parent_id=parent_block_id,
        range=target_range,
        type_=f"{ver}Network",  # pyright: ignore[reportArgumentType]
        name="Test Network 1",
        comment="Testing",
    )
    assert network["name"] == "Test Network 1"
    return network, target_range


@pytest.mark.parametrize(("prefix"), (("192.0.2.0", 24, "IPv4"), ("2001:DB8::", 32, "IPv6")))
def test_create_block_network_address(bluecat_test_data_cleared, api_instance, prefix):
    "test the happy path for creating blocks, networks, and addresses"
    # TODO: rename api methods to *_raw, implement convenience methods on top of them
    # which take IPNetwork / IPInterface objects to derive the necessary information

    addr, pfx_len, ver = prefix
    s: API = api_instance
    # to create a block we need to know the id of the parent block
    # we can get this by querying for the parent block
    parent = s.find_parent_block(addr)
    assert parent["range"] == f"{addr}/{pfx_len}".lower()
    assert "documentation" in parent["name"].lower()
    type_: Literal["IPv4Block", "IPv6Block"] = f"{ver}Block" # pyright: ignore[reportRedeclaration, reportAssignmentType]
    assert type_ in ["IPv4Block", "IPv6Block"]
    block = s.create_block(
        parent_id=parent["id"],
        comment="Testing",
        type_=type_,   # pyright: ignore[reportArgumentType]
        range=f"{addr}/{pfx_len+1}",
        name="Test Block 1",
    )
    assert block["name"] == "Test Block 1"

    with pytest.raises(RESTAPIError):
        # we can't create a block that overlaps with an existing block
        s.post(
            f"/blocks/{parent['id']}/blocks",
            comment="Testing",
            json=dict(type=f"{ver}Block", range=f"{addr}/{pfx_len}", name="Test Block 1"),
        )

    # to create a network we need to know the id of the parent network
    parent_block = s.find_parent_block(addr)
    network, target_range = _create_network(s, parent_block["id"], addr, pfx_len, ver)

    with pytest.raises(RESTAPIError):
        # we can't create a network that overlaps with an existing network
        s.post(
            f"/blocks/{parent_block['id']}/networks",
            comment="Testing",
            json=dict(type=f"{ver}Network", range=target_range, name="Test Network 1"),
        )

    # to create an address we need to know the id of the parent network
    parent_network = s.find_parent_network(addr)
    assert parent_network["id"] == network["id"]
    gw_kwargs: dict[str, Any] = dict(
        parent_id=network["id"],
        comment="Testing",
        type_=f"{ver}Address",
        state="GATEWAY",
        name="Test Gateway",
        address=str(IPAddress(addr) + 1),
    )
    if ver == "IPv6":
        with pytest.raises(RESTAPIError):
            # Bluecat does not allow IPV6 addresses with state `GATEWAY`
            s.create_address(**gw_kwargs)
        gw_kwargs["state"] = "STATIC"
        address = s.create_address(**gw_kwargs)
    else:
        address = s.create_address(**gw_kwargs)

    assert address["name"] == "Test Gateway"

    type_: Literal["IPv4Address", "IPv6Address"] = f"{ver}Address" # pyright: ignore[reportAssignmentType]
    assert type_ in ["IPv4Address", "IPv6Address"]
    static_addr = s.create_address( 
        address=str(IPAddress(addr) + 2),
        parent_id=network["id"],
        comment="Testing",
        type_=type_,
        state="STATIC",
        name="Test Address 1",
    ) 
    assert static_addr["address"] == str(IPAddress(addr) + 2)


def test_create_host_record(bluecat_test_data_cleared, api_instance):
    s: API = api_instance
    test_zone = s.get("/zones", params=dict(filter="absoluteName:'test.netmgmt.utsc.utoronto.ca'"))
    assert test_zone.status_code == 200
    test_zone = test_zone.json()["data"][0]
    assert test_zone["type"] == "Zone"
    assert test_zone["absoluteName"] == "test.netmgmt.utsc.utoronto.ca"
    # To create a host record, you need the bluecat IDs of all the ipaddress records it links to
    # so we create some addresses first

    v4_parent_block = s.find_parent_block("192.0.2.0")
    v4_network, _ = _create_network(s, v4_parent_block["id"], "192.0.2.0", 24, "IPv4")
    v4_addr = s.create_address(
        address="192.0.2.2",
        parent_id=v4_network["id"],
        type_="IPv4Address",
        comment="Testing",
        state="STATIC",
        name="Test Address 1",
    )
    v6_parent_block = s.find_parent_block("2001:DB8::")
    v6_network, _ = _create_network(s, v6_parent_block["id"], "2001:DB8::", 32, "IPv6")
    v6_addr = s.create_address(
        address="2001:DB8::2",
        parent_id=v6_network["id"],
        type_="IPv6Address",
        comment="Testing",
        state="STATIC",
        name="Test Address 1",
    )

    # now create the host record
    host_record = s.post(
        f"/zones/{test_zone['id']}/resourceRecords",
        comment="Testing",
        json=dict(
            name="host1",
            type="HostRecord",
            addresses=[
                {"id": v4_addr["id"], "type": "IPv4Address"},
                {"id": v6_addr["id"], "type": "IPv6Address"},
            ],
        ),
    )
    assert host_record.status_code == 201
    host_record = host_record.json()
    assert host_record["absoluteName"] == "host1.test.netmgmt.utsc.utoronto.ca"
