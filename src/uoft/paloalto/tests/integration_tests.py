import pytest
from ..conf import Settings


def test_address_groups():
    api = Settings.from_cache().get_api_connection()
    with api as s:
        r = s.get("/Objects/AddressGroups", params=dict(location="shared"))
        assert r.status_code == 200
        r = r.json()
        assert "result" in r
