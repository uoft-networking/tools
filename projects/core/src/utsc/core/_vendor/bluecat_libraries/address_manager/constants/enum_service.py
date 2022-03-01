# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Constants used in the ENUM services."""
from ._enum import StrEnum


class EnumServices(StrEnum):
    """Constants used in the ENUM services."""

    EMAIL_MAILTO = "email mailto"
    EMS_MAILTO = "ems mailto"
    EMS_TEL = "ems tel"
    FAX_TEL = "fax tel"
    FT_FTP = "ft ftp"
    H323 = "H323"
    IFAX_MAILTO = "ifax mailto"
    IM = "im"
    MMS_MAILTO = "mms mailto"
    MMS_TEL = "mms tel"
    PRES = "pres"
    PSTN_SIP = "pstn sip"
    PSTN_TEL = "pstn tel"
    SIP = "SIP"
    SMS_MAILTO = "sms mailto"
    SMS_TEL = "sms tel"
    VOICE_TEL = "voice tel"
    VPIM_LDAP = "VPIM LDAP"
    VPIM_MAILTO = "VPIM MAILTO"
    WEB_HTTP = "web http"
    WEB_HTTPS = "web https"
    XMPP = "xmpp"
