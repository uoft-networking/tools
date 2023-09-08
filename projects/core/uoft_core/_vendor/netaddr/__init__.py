#-----------------------------------------------------------------------------
#   Copyright (c) 2008 by David P. D. Moss. All rights reserved.
#
#   Released under the BSD license. See the LICENSE file for details.
#-----------------------------------------------------------------------------
"""A Python library for manipulating IP and EUI network addresses."""

#: Version info (major, minor, maintenance, status)
__version__ = '0.8.0'
VERSION = tuple(int(part) for part in __version__.split('.'))
STATUS = ''

import sys as _sys

if _sys.version_info[0:2] < (2, 4):
    raise RuntimeError('Python 2.4.x or higher is required!')

from .core import (AddrConversionError, AddrFormatError,
    NotRegisteredError, ZEROFILL, Z, INET_PTON, P, NOHOST, N)

from .ip import (IPAddress, IPNetwork, IPRange, all_matching_cidrs,
    cidr_abbrev_to_verbose, cidr_exclude, cidr_merge, iprange_to_cidrs,
    iter_iprange, iter_unique_ips, largest_matching_cidr,
    smallest_matching_cidr, spanning_cidr)

from .ip.sets import IPSet

from .ip.glob import (IPGlob, cidr_to_glob, glob_to_cidrs,
    glob_to_iprange, glob_to_iptuple, iprange_to_globs, valid_glob)

from .ip.nmap import valid_nmap_range, iter_nmap_range

from .ip.rfc1924 import base85_to_ipv6, ipv6_to_base85

from .eui import EUI, IAB, OUI

from .strategy.ipv4 import valid_str as valid_ipv4

from .strategy.ipv6 import (valid_str as valid_ipv6, ipv6_compact,
    ipv6_full, ipv6_verbose)

from .strategy.eui48 import (mac_eui48, mac_unix, mac_unix_expanded,
        mac_cisco, mac_bare, mac_pgsql, valid_str as valid_mac)

from .strategy.eui64 import (eui64_base, eui64_unix, eui64_unix_expanded,
        eui64_cisco, eui64_bare, valid_str as valid_eui64)

from .contrib.subnet_splitter import SubnetSplitter
