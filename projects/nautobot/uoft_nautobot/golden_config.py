from django.http import HttpRequest
from nautobot_golden_config.models import GoldenConfig
from django_jinja.backend import Jinja2
from jinja2 import Environment, StrictUndefined
from . import Settings
from nautobot.extras.models import GitRepository
from importlib. util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys


def _get_golden_config_repo_path():
    repo = GitRepository.objects.get(name="golden_config_templates")
    return Path(repo.filesystem_path)


def load_golden_config_module():
    models_module_name = "golden_config_models"
    repo_path = _get_golden_config_repo_path()
    models_module = repo_path / "golden_config_models.py"
    assert models_module.exists()
    spec = spec_from_file_location(models_module_name, models_module)
    module = module_from_spec(spec) # type: ignore
    sys.modules[models_module_name] = module
    spec.loader.exec_module(module) # type: ignore
    return module


def transposer(data):
    role = data["device_role"]["name"]
    models = load_golden_config_module()
    model_map = {
        "Access Switches": models.AccessSwitch,
        "Distribution Switches": models.DistributionSwitch,
    }
    model = model_map[role]
    data['sw'] = model.from_nautobot(data)
    return data


def noop_transposer(data):
    return data


def inject_secrets(
    intended_config: str, configs: GoldenConfig, request: HttpRequest
) -> str:
    """Takes a rendered IntendedConfig, treats it as a Jinja template, and injects secrets into it."""
    if not intended_config:
        return ""

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined

    s = Settings.from_cache()
    secrets = dict(
        enable_hash=encrypt_type9(s.ssh.enable_secret.get_secret_value()),
        admin_hash=encrypt_type9(s.ssh.admin.password.get_secret_value()),
        netdisco_snmp_pw=s.ssh.other["snmp_netdisco"].get_secret_value(),
    )

    template = jinja_env.from_string(intended_config)
    return template.render(**secrets)


# temporary code for inject_secrets post-processor
# This stuff is in the process of being upstreamed to nautobot
import base64
from hashlib import scrypt
import string
import secrets

ALPHABET = string.ascii_letters + string.digits
ENCRYPT_TYPE9_ENCODING_CHARS = "".join(
    ("./", string.digits, string.ascii_uppercase, string.ascii_lowercase)
)
BASE64_ENCODING_CHARS = "".join(
    (string.ascii_uppercase, string.ascii_lowercase, string.digits, "+/")
)


def type9_encode(data: bytes) -> str:
    encoding_translation_table = str.maketrans(
        BASE64_ENCODING_CHARS,
        ENCRYPT_TYPE9_ENCODING_CHARS,
    )
    res = base64.b64encode(data).decode().translate(encoding_translation_table)

    # and strip off the trailing '='
    res = res[:-1]
    return res


def type9_decode(data: str) -> bytes:
    encoding_translation_table = str.maketrans(
        ENCRYPT_TYPE9_ENCODING_CHARS,
        BASE64_ENCODING_CHARS,
    )
    # add back the trailing '='
    data += "=="
    res = data.translate(encoding_translation_table)
    res = base64.b64decode(res)
    return res


def encrypt_type9(unencrypted_password: str, salt: str | None = None) -> str:
    """Given an unencrypted password of Cisco Type 9 password, encypt it.

    Args:
        unencrypted_password: A password that has not been encrypted, and will be compared against.
        salt: a 14-character string that can be set by the operator. Defaults to random generated one.

    Returns:
        The encrypted password.

    Examples:
        >>> from netutils.password import encrypt_type9
        >>> encrypt_type7("123456")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
        >>> encrypt_type7("123456", "cvWdfQlRRDKq/U")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
    """

    if salt:
        if len(salt) != 14:
            raise ValueError("Salt must be 14 characters long.")
    else:
        # salt must always be a 14-byte-long printable string, often includes symbols
        salt = "".join(secrets.choice(ENCRYPT_TYPE9_ENCODING_CHARS) for _ in range(14))

    key = scrypt(
        unencrypted_password.encode(), salt=salt.encode(), n=2**14, r=1, p=1, dklen=32
    )

    # Cisco type 9 uses a different base64 encoding than the standard one, so we need to translate from
    # the standard one to the Cisco one.
    hash = type9_encode(key)

    return f"$9${salt}${hash}"


def _debug():
    pass
