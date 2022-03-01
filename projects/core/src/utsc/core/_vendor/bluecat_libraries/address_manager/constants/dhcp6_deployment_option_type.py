# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DHCPv6 Deployment Option API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DHCP6ClientDeploymentOptionType(StrEnum):
    """Values for types of DHCPv6 client options"""

    DNS_SERVERS = "dns-servers"
    DOMAIN_SEARCH_LIST = "domain-search-list"
    INFORMATION_REFRESH_TIME = "information-refresh-time"
    SNTP_SERVERS = "sntp-servers"
    UNICAST = "unicast"
    WPAD_URL = "wpad-url"
