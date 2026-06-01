from typing import TYPE_CHECKING
from pathlib import Path

from passlib.hash import sha512_crypt
from django.http import HttpRequest
from django_jinja.backend import Jinja2
from django.conf import settings
from jinja2 import Environment, StrictUndefined
from . import Settings

if TYPE_CHECKING:
    from nautobot_golden_config.models import GoldenConfig


# Temp hack until we can add support for this into the golden config plugin itself
from jinja2.sandbox import SandboxedEnvironment
from uoft.core.jinja import _update_env, import_from_module
import nautobot_golden_config.utilities.helper
import nautobot_golden_config.nornir_plays.config_intended
import nautobot_golden_config.api.views

# replacement for nautobot_golden_config.utilities.helper.get_django_env
def get_django_env():
    """Load Django Jinja filters from the Django jinja template engine, and add them to the jinja_env.

    Returns:
        SandboxedEnvironment
    """
    # import or re-import the filters module for each git repo, in case it has changed since the last time we imported it

    # Use a custom Jinja2 environment instead of Django's to avoid HTML escaping
    jinja_env = SandboxedEnvironment(**nautobot_golden_config.utilities.helper.JINJA_ENV)
    jinja_env.filters = nautobot_golden_config.utilities.helper.engines["jinja"].env.filters # pyright: ignore[reportAttributeAccessIssue]
    
    # bufix for timing bug: if get_django_env is called before any of the git repository datasources 
    # are loaded, then the filters won't be loaded yet and we need to load them here
    for filter_file in Path(settings.GIT_ROOT).glob('**/filters.py'):
        import_from_module(filter_file.parent, force=False)

    _update_env(jinja_env)
    return jinja_env

nautobot_golden_config.utilities.helper.get_django_env = get_django_env
nautobot_golden_config.nornir_plays.config_intended.get_django_env = get_django_env
nautobot_golden_config.api.views.get_django_env = get_django_env

def transposer(data: dict):
    """This function exists to pre-process graphql data before it's passed to the jinja template."""
    # The data dict returned here will be expanded into the jinja template's context.
    # Each key in the dict will be a variable in the template.
    # This is fine for most use cases, but if you need to write a filter that references multiple variables,
    # it can be pretty dang cumbersome.
    # with this transposer, we simply copy the data dict into itself,
    # so that filters can access the whole thing as a single variable
    data["data"] = data.copy()  # important to copy, not just assign, otherwise we get infinite recursion

    return data


def noop_transposer(data):
    return data


def inject_secrets(intended_config: str, configs: "GoldenConfig", request: HttpRequest) -> str:
    """Takes a rendered IntendedConfig, treats it as a Jinja template, and injects secrets into it."""
    if not intended_config:
        return ""

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined

    s = Settings.from_cache()
    secrets = dict(
        enable_sha512=sha512_crypt.using(rounds=5000).hash(s.ssh.enable_secret.get_secret_value()),
        admin_sha512=sha512_crypt.using(rounds=5000).hash(s.ssh.admin.password.get_secret_value()),
        netdisco_snmp_pw=s.ssh.other["snmp_netdisco"].get_secret_value(),
        radius_key_cisco_ciphertext_1=s.ssh.other["radius_key_cisco_ciphertext_1"].get_secret_value(),
        radius_key_cisco_ciphertext_2=s.ssh.other["radius_key_cisco_ciphertext_2"].get_secret_value(),
        radius_arista_dc_fabric=s.ssh.other["radius_arista_dc_fabric"].get_secret_value(),
        radius_arista_loopbacks=s.ssh.other["radius_arista_loopbacks"].get_secret_value(),
        radius_arista_oob=s.ssh.other["radius_arista_oob"].get_secret_value(),
        radius_arista_vl900=s.ssh.other["radius_arista_vl900"].get_secret_value(),
    )

    template = jinja_env.from_string(intended_config)
    return template.render(**secrets)
