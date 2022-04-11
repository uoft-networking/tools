"""Nautobot development configuration file."""
import os
from subprocess import CalledProcessError
import sys
from pathlib import Path

from nautobot.core.settings import *  # noqa: F403
from nautobot.core.settings_funcs import is_truthy, parse_redis_connection
from utsc.core import shell
import debugpy

#
# Misc. settings
#

ALLOWED_HOSTS = os.getenv("NAUTOBOT_ALLOWED_HOSTS", "").split(" ")
SECRET_KEY = os.getenv("NAUTOBOT_SECRET_KEY", "")

PLUGINS = ["nautobot_utsc", "nautobot_ssot"]
PLUGINS_CONFIG = {
    "nautobot_utsc": {
        "bluecat": {
            "url": os.getenv("NAUTOBOT_BLUECAT_URL", ""),
            "username": os.getenv("NAUTOBOT_BLUECAT_USERNAME", ""),
            "password_cmd": os.getenv("NAUTOBOT_BLUECAT_PASSWORD_CMD", ""),
        }
    },
    "nautobot_ssot": {
        "hide_example_jobs": True,
    },
}

AUTHENTICATION_BACKENDS = [
    'django_auth_ldap.backend.LDAPBackend',
    'nautobot.core.authentication.ObjectPermissionBackend',
]

import ldap

# Server URI
AUTH_LDAP_SERVER_URI = os.getenv("AUTH_LDAP_SERVER_URI", "ldaps://utscadlb.utsc.utoronto.ca")

# The following may be needed if you are binding to Active Directory.
AUTH_LDAP_CONNECTION_OPTIONS = {
    ldap.OPT_REFERRALS: 0
}


# Set the DN and password for the Nautobot service account.
AUTH_LDAP_BIND_DN = "CN=nautobotbind,OU=ServiceAccounts,OU=Unmanaged,DC=utscad,DC=utsc,DC=utoronto,DC=ca"

def get_ldap_default_pass():
    p = Path('/run/secrets/ldap_bind_password')
    if p.exists():
        return p.read_text()
    try:
        shell("pass utsc/nautobot-ldap").splitlines()[0]
    except CalledProcessError:
        return ""

AUTH_LDAP_BIND_PASSWORD = os.getenv("AUTH_LDAP_BIND_PASSWORD", get_ldap_default_pass())

# Include this `ldap.set_option` call if you want to ignore certificate errors. This might be needed to accept a self-signed cert.
ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

# This search matches users with the sAMAccountName equal to the provided username. This is required if the user's
# username is not in their DN (Active Directory).
# AUTH_LDAP_USER_SEARCH = LDAPSearch("dc=utsc,dc=utoronto,dc=ca",
#                                     ldap.SCOPE_SUBTREE,
#                                     "(sAMAccountName=%(user)s)")

# If a user's DN is producible from their username, we don't need to search.
AUTH_LDAP_USER_DN_TEMPLATE = "CN=%(user)s,OU=UTORIDStaff,OU=Staff Users,DC=utscad,DC=utsc,DC=utoronto,DC=ca"

# You can map user attributes to Django attributes as so.
AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": "givenName",
    "last_name": "sn",
    "email": "mail"
}

# This search ought to return all groups to which the user belongs. django_auth_ldap uses this to determine group
# hierarchy.
AUTH_LDAP_GROUP_SEARCH = LDAPSearch("OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca", ldap.SCOPE_SUBTREE,
                                    "(objectClass=group)")
AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()

AUTH_LDAP_REQUIRE_GROUP = "CN=GL_IITS_Users,OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca"

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_active": "CN=GL_IITS_Users,OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca",
    "is_staff": "CN=GL_SysNetAdmins,OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca",
    "is_superuser": "CN=GL_SysNet_SuperUsers,OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca"
}

# For more granular permissions, we can map LDAP groups to Django groups.
AUTH_LDAP_FIND_GROUP_PERMS = True

#
# Databases
#

DATABASES = {
    "default": {
        "NAME": os.getenv("NAUTOBOT_DB_NAME", "nautobot"),
        "USER": os.getenv("NAUTOBOT_DB_USER", ""),
        "PASSWORD": os.getenv("NAUTOBOT_DB_PASSWORD", ""),
        "HOST": os.getenv("NAUTOBOT_DB_HOST", "localhost"),
        "PORT": os.getenv("NAUTOBOT_DB_PORT", ""),
        "CONN_MAX_AGE": int(os.getenv("NAUTOBOT_DB_TIMEOUT", 300)),
        "ENGINE": os.getenv("NAUTOBOT_DB_ENGINE", "django.db.backends.postgresql"),
    }
}

# Ensure proper Unicode handling for MySQL
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4"}

#
# Debug
#

DEBUG = is_truthy(os.getenv("NAUTOBOT_DEBUG", True))

try:
    debugpy.listen(('0.0.0.0', 5678))
except:
    pass

# Django Debug Toolbar
DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda _request: DEBUG and not TESTING}

if "debug_toolbar" not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.append("debug_toolbar")  # noqa: F405
if "debug_toolbar.middleware.DebugToolbarMiddleware" not in MIDDLEWARE:  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

#
# Logging
#

LOG_LEVEL = "DEBUG" if DEBUG else "INFO"

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

# Verbose logging during normal development operation, but quiet logging during unit test execution
if not TESTING:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "normal": {
                "format": "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s :\n  %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "verbose": {
                "format": "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-20s %(filename)-15s %(funcName)30s() :\n  %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "normal_console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "normal",
            },
            "verbose_console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "loggers": {
            "django": {"handlers": ["normal_console"], "level": "INFO"},
            "nautobot": {
                "handlers": ["verbose_console" if DEBUG else "normal_console"],
                "level": LOG_LEVEL,
            },
            "rq.worker": {
                "handlers": ["verbose_console" if DEBUG else "normal_console"],
                "level": LOG_LEVEL,
            },
            'django_auth_ldap': {
                'handlers': ["verbose_console" if DEBUG else "normal_console"],
                'level': 'DEBUG',
            },
        },
    }

#
# Redis
#

# The django-redis cache is used to establish concurrent locks using Redis. The
# django-rq settings will use the same instance/database by default.
#
# This "default" server is now used by RQ_QUEUES.
# >> See: nautobot.core.settings.RQ_QUEUES
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": parse_redis_connection(redis_database=0),
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# RQ_QUEUES is not set here because it just uses the default that gets imported
# up top via `from nautobot.core.settings import *`.

# Redis Cacheops
CACHEOPS_REDIS = parse_redis_connection(redis_database=1)

#
# Celery settings are not defined here because they can be overloaded with
# environment variables. By default they use `CACHES["default"]["LOCATION"]`.
#
