from uoft_scripts import _sync
import pickle
from pathlib import Path

import pytest
from pytest_mock import MockerFixture


@pytest.fixture()
def mock_sync_data(mocker: MockerFixture):
    fixtures = Path(__file__).parent / "fixtures/_private"
    fixtures.mkdir(exist_ok=True, parents=True)

    bluecat_orig = _sync.BluecatTarget.load_data_raw

    def bluecat_load(self, datasets):
        target_data_file = (
            fixtures / f"bluecat_{'-'.join(sorted(list(datasets)))}_raw.pkl"
        )
        if target_data_file.exists():
            print('loading from file')
            with open(target_data_file, "rb") as f:
                return pickle.load(f)
        else:
            print('loading from bluecat')
            data = bluecat_orig(self, datasets)
            with open(target_data_file, "wb") as f:
                pickle.dump(data, f)
            return data

    mocker.patch("uoft_scripts._sync.BluecatTarget.load_data_raw", new=bluecat_load)

    nautobot_orig = _sync.NautobotTarget.load_data_raw

    def nautobot_load(self, datasets):
        target_data_file = (
            fixtures / f"nautobot_{'-'.join(sorted(list(datasets)))}_raw.pkl"
        )

        if target_data_file.exists():
            with open(target_data_file, "rb") as f:
                return pickle.load(f)
        else:
            data = nautobot_orig(self, datasets)
            with open(target_data_file, "wb") as f:
                pickle.dump(data, f)
            return data

    mocker.patch("uoft_scripts._sync.NautobotTarget.load_data_raw", new=nautobot_load)

    mocker.patch("uoft_scripts._sync.NautobotTarget.delete_one", return_value=None)


def test_bluecat_load_data(mock_sync_data):
    datasets = {"prefixes", "addresses"}
    bc = _sync.BluecatTarget()
    bc.load_data(datasets) # type: ignore
    assert bc.syncdata.prefixes
    assert len(bc.syncdata.prefixes) > 0
    assert bc.syncdata.addresses
    assert len(bc.syncdata.addresses) > 0


def test_sync_data(mock_sync_data, mocker):

    datasets = {"prefixes", "addresses"}
    bc = _sync.BluecatTarget()
    nb = _sync.NautobotTarget(dev=True)
    sm = _sync.SyncManager(bc, nb, datasets, on_orphan="skip")  # type: ignore

    sm.load()
    sm.synchronize()
    sm.commit()
    # with mocker.patch("uoft_scripts._sync.NautobotTarget.api"):
    #     sm.commit()
    #     assert nb.api.ipam.ip_addresses.create.call_count > 1
    #     assert nb.api.ipam.prefixes.create.call_count > 1


def test_bluecat_create(mock_sync_data):
    bc = _sync.BluecatTarget()
    bc.load_data({"prefixes", "addresses"})
    changes = _sync.Changes(
        create=dict(
            prefixes={
                "192.0.2.0/25": _sync.PrefixModel(
                    prefix="192.0.2.0/25",
                    description="test 1",
                    type="container",
                    status="Active",
                ),
                "192.0.2.128/25": _sync.PrefixModel(
                    prefix="192.0.2.128/25",
                    description="test 2",
                    type="network",
                    status="Reserved",
                ),
                "2001:DB8:AAAA::/48": _sync.PrefixModel(
                    prefix="2001:DB8:AAAA::/48",
                    description="test 3",
                    type="container",
                    status="Active",
                ),
                "2001:DB8:AAAA:BBBB::/64": _sync.PrefixModel(
                    prefix="2001:DB8:AAAA:BBBB::/64",
                    description="test 3",
                    type="network",
                    status="Deprecated",
                ),
            },
            addresses={
                '192.0.2.1': _sync.IPAddressModel(
                    address='192.0.2.1',
                    prefixlen=25,
                    name='router1',
                    status='Active',
                    dns_name='test-router1.netmgmt.utsc.utoronto.ca'
                ),
                '192.0.2.5': _sync.IPAddressModel(
                    address='192.0.2.5',
                    prefixlen=25,
                    name='host1',
                    status='Deprecated',
                    dns_name='host1.netmgmt.utsc.utoronto.ca'
                ),
                '2001:DB8:AAAA:BBBB::1': _sync.IPAddressModel(
                    address='2001:DB8:AAAA::1',
                    prefixlen=48,
                    name='router2',
                    status='Active',
                    dns_name='router2.netmgmt.utsc.utoronto.ca'
                ),
                '2001:DB8:AAAA:BBBB::5': _sync.IPAddressModel(
                    address='2001:DB8:AAAA::5',
                    prefixlen=48,
                    name='host2',
                    status='Reserved',
                    dns_name='host2.netmgmt.utsc.utoronto.ca'
                ),
            }
        )
    )
    bc.create(changes.create)
    print()
