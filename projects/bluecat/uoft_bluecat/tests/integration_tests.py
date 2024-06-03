from .. import Settings, ALL_NETWORK_TYPES

import pytest


@pytest.fixture()
def bluecat_test_data_cleared():
    """Clear all test prefixes (prefixes inside the IPv4 and IPv6 documentation ranges)
    and all records from the test zone (test.netmgmt.utsc.utoronto.ca) from the Bluecat server
    """
    from uoft_core._vendor.bluecat_libraries.http_client.exceptions import ErrorResponse
    from requests import Session

    s = Settings.from_cache()
    sess = Session()
    url = f'{s.url}/api/v2'
    tok_data = sess.post(f'{url}/sessions', json={"username": s.username, "password": s.password}).json()
    # tok_data contains an apiToken field
    # you would think that the api token would be a valid Bearer token, but it's not
    # using it as such produces a 401 error 
    # thanks bluecat!
    # token = tok_data['apiToken']
    # tok_data also contains a basicAuthenticationCredentials field
    # which is a base64 encoded string of the form "username:token"
    credentials = tok_data['basicAuthenticationCredentials']
    sess.headers.update({"Authorization": f"Basic {credentials}"})
    sess.headers.update({"Accept": "application/hal+json"})
    r = sess.get(f"{url}/")

    api = s.get_api_connection()
    ipv4_doc_prefix = api.client.get_entity_by_cidr(
        api.configuration_id, "192.0.2.0/24", api.constants.ObjectType.IP4_BLOCK
    )
    ipv6_doc_prefix = api.client.get_entity_by_prefix(
        api.configuration_id, "2001:DB8::/32", api.constants.ObjectType.IP6_BLOCK
    )
    for prefix in [ipv4_doc_prefix, ipv6_doc_prefix]:
        for typ in ALL_NETWORK_TYPES:
            try:
                for entity in api.client.get_entities(prefix["id"], typ):
                    api.client.delete_entity(entity["id"])
            except ErrorResponse as e:
                pass

    test_zone = api.client.get_entity_by_name(
        api.configuration_id,
        "test",
        api.constants.ObjectType.ZONE,
    )
    for entity in api.client.get_entities(test_zone["id"], api.constants.ObjectType.ENTITY):
        api.client.delete_entity(entity["id"])


def test_some(bluecat_test_data_cleared):
    api = Settings.from_cache().get_api_connection()
    print()
