from pickle import load, dump

from . import config

from uoft_core._vendor.bluecat_libraries.address_manager.api import Client
from uoft_core._vendor.bluecat_libraries.address_manager.constants import ObjectType
from uoft_core import Timeit


def collect(include_addresses=False):
    """Collect network data from Bluecat API"""
    client = Client(url=config.data.bluecat.url)
    client.login(
        username=config.data.bluecat.username,
        password=config.data.bluecat.password,
    )
    root_object_id = client.get_entities(0, ObjectType.CONFIGURATION)[0]["id"]
    if include_addresses:
        container_types = [
            ObjectType.IP4_BLOCK,
            ObjectType.IP6_BLOCK,
            ObjectType.IP4_NETWORK,
            ObjectType.IP6_NETWORK,
            ObjectType.IP4_IP_GROUP,
        ]
        all_types = [
            ObjectType.IP4_ADDRESS,
            ObjectType.IP6_ADDRESS,
        ] + container_types
    else:
        container_types = [
            ObjectType.IP4_BLOCK,
            ObjectType.IP6_BLOCK,
        ]
        all_types = [
            ObjectType.IP4_NETWORK,
            ObjectType.IP6_NETWORK,
            ObjectType.IP4_IP_GROUP,
        ] + container_types

    def get_all_entities(parent_id, typ, start=0):
        page_size = 100
        entities = client.get_entities(parent_id, typ, start=start, count=page_size)
        yield from entities
        if len(entities) == page_size:
            print("paging...")
            yield from get_all_entities(parent_id, typ, start=start + page_size)

    def yield_ip_object_tree(parent_id):
        for typ in all_types:
            for entity in get_all_entities(parent_id, typ):
                if typ in container_types:
                    print(f"{typ} {entity['name']}")
                    yield dict(
                        entity, children=list(yield_ip_object_tree(entity["id"]))
                    )
                else:
                    yield entity

    def yield_ip_object_list(parent_id):
        for typ in all_types:
            for entity in get_all_entities(parent_id, typ):
                yield entity
                if typ in container_types:
                    print(f"{typ} {entity['name']}")
                    yield from yield_ip_object_list(entity["id"])

    clock = Timeit()
    t = list(yield_ip_object_list(root_object_id))
    fname = "bluecat-all.pkl" if include_addresses else "bluecat-no-addresses.pkl"
    with open(fname, "wb") as f:
        dump(t, f)
    print(f"Wrote {len(t)} objects to {fname} in {clock.stop().str}")


def main():
    collect()
