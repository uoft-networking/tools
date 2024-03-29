import platform

import pytest

from ... import iprange_to_cidrs, IPNetwork, IPAddress, INET_PTON, AddrFormatError
from ...strategy.ipv6 import int_to_str


@pytest.mark.skipif('sys.platform != "darwin"')
def test_ip_behaviour_osx():
    assert iprange_to_cidrs('::1', '::255.255.255.254') == [
        IPNetwork('::1/128'),
        IPNetwork('::0.0.0.2/127'),
        IPNetwork('::0.0.0.4/126'),
        IPNetwork('::0.0.0.8/125'),
        IPNetwork('::0.0.0.16/124'),
        IPNetwork('::0.0.0.32/123'),
        IPNetwork('::0.0.0.64/122'),
        IPNetwork('::0.0.0.128/121'),
        IPNetwork('::0.0.1.0/120'),
        IPNetwork('::0.0.2.0/119'),
        IPNetwork('::0.0.4.0/118'),
        IPNetwork('::0.0.8.0/117'),
        IPNetwork('::0.0.16.0/116'),
        IPNetwork('::0.0.32.0/115'),
        IPNetwork('::0.0.64.0/114'),
        IPNetwork('::0.0.128.0/113'),
        IPNetwork('::0.1.0.0/112'),
        IPNetwork('::0.2.0.0/111'),
        IPNetwork('::0.4.0.0/110'),
        IPNetwork('::0.8.0.0/109'),
        IPNetwork('::0.16.0.0/108'),
        IPNetwork('::0.32.0.0/107'),
        IPNetwork('::0.64.0.0/106'),
        IPNetwork('::0.128.0.0/105'),
        IPNetwork('::1.0.0.0/104'),
        IPNetwork('::2.0.0.0/103'),
        IPNetwork('::4.0.0.0/102'),
        IPNetwork('::8.0.0.0/101'),
        IPNetwork('::16.0.0.0/100'),
        IPNetwork('::32.0.0.0/99'),
        IPNetwork('::64.0.0.0/98'),
        IPNetwork('::128.0.0.0/98'),
        IPNetwork('::192.0.0.0/99'),
        IPNetwork('::224.0.0.0/100'),
        IPNetwork('::240.0.0.0/101'),
        IPNetwork('::248.0.0.0/102'),
        IPNetwork('::252.0.0.0/103'),
        IPNetwork('::254.0.0.0/104'),
        IPNetwork('::255.0.0.0/105'),
        IPNetwork('::255.128.0.0/106'),
        IPNetwork('::255.192.0.0/107'),
        IPNetwork('::255.224.0.0/108'),
        IPNetwork('::255.240.0.0/109'),
        IPNetwork('::255.248.0.0/110'),
        IPNetwork('::255.252.0.0/111'),
        IPNetwork('::255.254.0.0/112'),
        IPNetwork('::255.255.0.0/113'),
        IPNetwork('::255.255.128.0/114'),
        IPNetwork('::255.255.192.0/115'),
        IPNetwork('::255.255.224.0/116'),
        IPNetwork('::255.255.240.0/117'),
        IPNetwork('::255.255.248.0/118'),
        IPNetwork('::255.255.252.0/119'),
        IPNetwork('::255.255.254.0/120'),
        IPNetwork('::255.255.255.0/121'),
        IPNetwork('::255.255.255.128/122'),
        IPNetwork('::255.255.255.192/123'),
        IPNetwork('::255.255.255.224/124'),
        IPNetwork('::255.255.255.240/125'),
        IPNetwork('::255.255.255.248/126'),
        IPNetwork('::255.255.255.252/127'),
        IPNetwork('::255.255.255.254/128'),
    ]

    #   inet_pton has to be different on Mac OSX *sigh*...
    assert IPAddress('010.000.000.001', flags=INET_PTON) == IPAddress('10.0.0.1')
    # ...but at least Apple changed inet_ntop in Mac OS 10.15 (Catalina) so it's compatible with Linux
    if platform.mac_ver()[0] >= '10.15':
        assert int_to_str(0xffff) == '::ffff'
    else:
        assert int_to_str(0xffff) == '::0.0.255.255'


@pytest.mark.skipif('sys.platform == "darwin"')
def test_ip_behaviour_non_osx():
    assert iprange_to_cidrs('::1', '::255.255.255.254') == [
        IPNetwork('::1/128'),
        IPNetwork('::2/127'),
        IPNetwork('::4/126'),
        IPNetwork('::8/125'),
        IPNetwork('::10/124'),
        IPNetwork('::20/123'),
        IPNetwork('::40/122'),
        IPNetwork('::80/121'),
        IPNetwork('::100/120'),
        IPNetwork('::200/119'),
        IPNetwork('::400/118'),
        IPNetwork('::800/117'),
        IPNetwork('::1000/116'),
        IPNetwork('::2000/115'),
        IPNetwork('::4000/114'),
        IPNetwork('::8000/113'),
        IPNetwork('::0.1.0.0/112'),
        IPNetwork('::0.2.0.0/111'),
        IPNetwork('::0.4.0.0/110'),
        IPNetwork('::0.8.0.0/109'),
        IPNetwork('::0.16.0.0/108'),
        IPNetwork('::0.32.0.0/107'),
        IPNetwork('::0.64.0.0/106'),
        IPNetwork('::0.128.0.0/105'),
        IPNetwork('::1.0.0.0/104'),
        IPNetwork('::2.0.0.0/103'),
        IPNetwork('::4.0.0.0/102'),
        IPNetwork('::8.0.0.0/101'),
        IPNetwork('::16.0.0.0/100'),
        IPNetwork('::32.0.0.0/99'),
        IPNetwork('::64.0.0.0/98'),
        IPNetwork('::128.0.0.0/98'),
        IPNetwork('::192.0.0.0/99'),
        IPNetwork('::224.0.0.0/100'),
        IPNetwork('::240.0.0.0/101'),
        IPNetwork('::248.0.0.0/102'),
        IPNetwork('::252.0.0.0/103'),
        IPNetwork('::254.0.0.0/104'),
        IPNetwork('::255.0.0.0/105'),
        IPNetwork('::255.128.0.0/106'),
        IPNetwork('::255.192.0.0/107'),
        IPNetwork('::255.224.0.0/108'),
        IPNetwork('::255.240.0.0/109'),
        IPNetwork('::255.248.0.0/110'),
        IPNetwork('::255.252.0.0/111'),
        IPNetwork('::255.254.0.0/112'),
        IPNetwork('::255.255.0.0/113'),
        IPNetwork('::255.255.128.0/114'),
        IPNetwork('::255.255.192.0/115'),
        IPNetwork('::255.255.224.0/116'),
        IPNetwork('::255.255.240.0/117'),
        IPNetwork('::255.255.248.0/118'),
        IPNetwork('::255.255.252.0/119'),
        IPNetwork('::255.255.254.0/120'),
        IPNetwork('::255.255.255.0/121'),
        IPNetwork('::255.255.255.128/122'),
        IPNetwork('::255.255.255.192/123'),
        IPNetwork('::255.255.255.224/124'),
        IPNetwork('::255.255.255.240/125'),
        IPNetwork('::255.255.255.248/126'),
        IPNetwork('::255.255.255.252/127'),
        IPNetwork('::255.255.255.254/128'),
    ]

    #   Sadly, inet_pton cannot help us here ...
    with pytest.raises(AddrFormatError):
        IPAddress('010.000.000.001', flags=INET_PTON)

    assert int_to_str(0xffff) == '::ffff'
