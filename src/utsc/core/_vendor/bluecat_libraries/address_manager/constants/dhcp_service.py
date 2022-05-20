# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DHCP service options API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DHCPServiceOption(StrEnum):
    """Constants used in the DHCP service option methods."""

    ALLOW_DHCP_CLASS_MEMBERS = "allow-dhcp-class-members"
    ALLOW_MAC_POOL = "allow-mac-pool"
    ALWAYS_BROADCAST = "always-broadcast"
    ALWAYS_REPLY_RFC1048 = "always-reply-rfc1048"
    APPLY_MAC_AUTHENTICATION_POLICY = "apply-mac-authentication-policy"
    CLIENT_UPDATES = "client-updates"
    CONFLICT_DETECTION = "conflict-detection"
    DDNS_DOMAINNAME = "ddns-domainname"
    DDNS_DUAL_STACK_MIXED_MODE = "ddns-dual-stack-mixed-mode"
    DDNS_GUARD_ID_MUST_MATCH = "ddns-guard-id-must-match"
    DDNS_HOSTNAME = "ddns-hostname"
    DDNS_REV_DOMAINNAME = "ddns-rev-domainname"
    DDNS_TTL = "ddns-ttl"
    DDNS_UPDATES = "ddns-updates"
    DDNS_UPDATE_STYLE = "ddns-update-style"
    DEFAULT_LEASE_TIME = "default-lease-time"
    DENY_DHCP_CLASS_MEMBERS = "deny-dhcp-class-members"
    DENY_DHCP_CLIENTS = "deny-dhcp-clients"
    DENY_MAC_POOL = "deny-mac-pool"
    DDNS_OTHER_GUARD_IS_DYNAMIC = "ddns-other-guard-is-dynamic"
    DENY_UNKNOWN_MAC_ADDRESSES = "deny-unknown-mac-addresses"
    DHCP_CLASS_LEASE_LIMIT = "dhcp-class-lease-limit"
    DO_REVERSE_UPDATES = "do-reverse-updates"
    DYNAMIC_BOOTP_LEASE_LENGTH = "dynamic-bootp-lease-length"
    FILENAME = "filename"
    GET_LEASE_HOSTNAMES = "get-lease-hostnames"
    LOAD_BALANCE_OVERRIDE = "load-balance-override"
    LOAD_BALANCE_SPLIT = "load-balance-split"
    MAX_LEASE_TIME = "max-lease-time"
    MAX_RESPONSE_DELAY = "max-response-delay"
    MAX_UNACKED_UPDATES = "max-unacked-updates"
    MCLT = "mclt"
    MIN_LEASE_TIME = "min-lease-time"
    MIN_SECS = "min-secs"
    NEXT_SERVER = "next-server"
    ONE_LEASE_PER_CLIENT = "one-lease-per-client"
    PING_CHECK = "ping-check"
    SERVER_IDENTIFIER = "server-identifier"
    SITE_OPTION_SPACE = "site-option-space"
    STASH_AGENT_OPTIONS = "stash-agent-options"
    UPDATE_CONFLICT_DETECTION = "update-conflict-detection"
    UPDATE_OPTIMIZATION = "update-optimization"
    UPDATE_STATIC_LEASES = "update-static-leases"
    USE_LEASE_ADDR_FOR_DEFAULT_ROUTE = "use-lease-addr-for-default-route"


class DHCPServiceOptionConstant(StrEnum):
    """
    Values used in DHCP service options. Depending on the type of deployment option being added,
    the format of the value input might differ.
    """

    DDNS_HOSTNAME_POSITION_APPEND = "append"
    DDNS_HOSTNAME_POSITION_PREPEND = "prepend"
    DDNS_HOSTNAME_TYPE_DUID = "duid"
    DDNS_HOSTNAME_TYPE_FIXED = "fixed"
    DDNS_HOSTNAME_TYPE_IP = "ip"
    DDNS_HOSTNAME_TYPE_MAC = "mac"
    DDNS_UPDATE_STYLE_INTERIM = "interim"
    DDNS_UPDATE_STYLE_STANDARD = "standard"
