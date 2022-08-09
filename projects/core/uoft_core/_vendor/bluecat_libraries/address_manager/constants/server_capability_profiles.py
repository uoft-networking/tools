# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in POST /v1/addServer method in BlueCat Address Manager."""
from ._enum import StrEnum


class ServerCapabilityProfiles(StrEnum):
    """Values for types of server profiles in BlueCat Address Manager."""

    ADONIS_800 = "ADONIS_800"
    ADONIS_1200 = "ADONIS_1200"
    ADONIS_1900 = "ADONIS_1900"
    ADONIS_1950 = "ADONIS_1950"
    ADONIS_XMB2 = "ADONIS_XMB2"
    ADONIS_XMB3 = "ADONIS_XMB3"
    AFILIAS_DNS_SERVER = "AFILIAS_DNS_SERVER"
    DNS_DHCP_SERVER_20 = "DNS_DHCP_SERVER_20"
    DNS_DHCP_SERVER_45 = "DNS_DHCP_SERVER_45"
    DNS_DHCP_SERVER_60 = "DNS_DHCP_SERVER_60"
    DNS_DHCP_SERVER_100 = "DNS_DHCP_SERVER_100"
    DNS_DHCP_SERVER_100_D = "DNS_DHCP_SERVER_100_D"
    DNS_DHCP_GEN4_7000 = "DNS_DHCP_GEN4_7000"
    DNS_DHCP_GEN4_5000 = "DNS_DHCP_GEN4_5000"
    DNS_DHCP_GEN4_4000 = "DNS_DHCP_GEN4_4000"
    DNS_DHCP_GEN4_2000 = "DNS_DHCP_GEN4_2000"
    OTHER_DNS_SERVER = "OTHER_DNS_SERVER"
