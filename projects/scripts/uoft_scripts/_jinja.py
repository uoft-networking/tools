from textwrap import indent, dedent
from typing import Literal
from hashlib import shake_128
from jinja2.sandbox import SandboxedEnvironment
from jinja2.runtime import Context
from jinja2 import FileSystemLoader, pass_context
from pathlib import Path
import sys
import ipaddress
import re
from importlib.util import spec_from_file_location, module_from_spec
from base64 import b64encode
import inspect
from box import Box
from uoft_core import compile_source_code
from uoft_core.types import Field
import uoft_core.jinja_library as library
from uoft_ssh import Settings as SSHSettingsBase, Credentials



class SSHSettings(SSHSettingsBase):
    nautobot: Credentials = Field(
        description="Credentials for the Nautobot user, typically has read-only access."
    )

# At import time, we need to import filters defined in git repositories
def _hash_path(path: Path):
    """Converts a path to a unique-ish valid python identifier / module name"""
    return b64encode(path.stem.encode()).decode().replace("/", "").replace("+", "").replace("=", "")

def repo_filters_module_name(repo_path: Path):
    return "jinja_filters_from_git_repo_" + _hash_path(repo_path)

def import_repo_filters_module(repo_path: Path, force=False):
    module_name = repo_filters_module_name(repo_path)
    module_file = repo_path / "filters.py"
    if not module_file.exists():
        # Skip if this repo doesn't have a filters.py
        return None
    if module_name in sys.modules and not force:
        # Skip if this module has already been imported
        return sys.modules[module_name]
    spec = spec_from_file_location(module_name, module_file)
    module = module_from_spec(spec) # type: ignore
    sys.modules[module_name] = module
    spec.loader.exec_module(module) # type: ignore
    return module

@library.filter
def load_local_jinja_library(_):
    # in nautobot, this filter would dynamically find the root of the templates git repo
    # load the filters.py file, and import it as a module
    # find the currently-running Jinja environment, override some of its otherwise-inaccessible settings
    # and inject the filters from the imported module into the environment
    # this is a bit of a hack, but it's the only way to dynamically load filters from a git repo in nautobot golden config
    # here in uoft-scripts, none of that is necessary and this filter is a no-op

    # because this is a filter, we need to return something,
    # something that won't show up in the rendered output
    return ""

@library.filter
def config_path(obj):
    "returns an ideal file path to store the rendered/backed-up config for a given object"
    folder_name = "device-location-missing"
    if obj.location:
        if obj.location.location_type.name == "Building":
            building = obj.location
        else:
            building = obj.location.parent
        folder_name = building.cf['building_code']
    ext = "txt"
    if obj.platform:
        match obj.platform.network_driver:
            case 'arista_eos':
                ext = "eos.cfg"
            case 'cisco_ios':
                ext = "ios.cfg"
            case 'aruba_aoscx':
                ext = "aoscx.cfg"
            case 'cisco_nxos':
                ext = "nxos.cfg"
            case 'cisco_xr':
                ext = "iosxr.cfg"
            case 'juniper_junos':
                ext = "junos.cfg"
            case 'vyos':
                ext = "vyos.cfg"
            case _:
                ext = "txt"

    return f"{folder_name}/{obj.name}.{ext}"


@library.filter
def reindent(text: str, spaces: int):
    """
    dedents a block of text from its current indentation level to zero,
    and then indents that block of text by a given number of spaces
    """
    return indent(dedent(str(text)), " " * spaces)


@library.filter
def derive_type9_password(hostname, password_variant: Literal['enable', 'admin']):
    """Derives a type 9 password from a given switch object and a password variant"""

    s = SSHSettings.from_cache()
    if password_variant == 'enable':
        password = s.enable_secret.get_secret_value()
    elif password_variant == 'admin':
        password = s.admin.password.get_secret_value()
    else:
        raise ValueError(f"Invalid password variant: {password_variant}")

    # convert variable-length switch name to 14 bytes of cisco-compatible salt
    salt = type9_encode(shake_128(hostname.encode()).digest(14))[:14]
    return encrypt_type9(password, salt=salt)


@library.filter
@pass_context
def python_eval(ctx: Context, code_block: str):
    """Evaluates a block of python code in the context of the current template"""
    code_block = dedent(code_block)
    function_definition = "def virtual_function():\n" + indent(code_block, "    ")
    global_vars = Box(ctx.environment.globals)
    global_vars.update(ctx.environment.filters)
    global_vars.update(ctx.environment.tests)
    global_vars.update(dict(ipaddress=ipaddress, re=re))
    template_frame = None
    for frameinfo in inspect.stack():
        if frameinfo.filename.endswith(".j2"):
            template_frame = frameinfo.frame
            break
    assert template_frame is not None
    for k, v in template_frame.f_locals.items():
        # template frame context vars are prefixed with jinja state machine identifiers.
        # These identifiers all follow a patern of <letter>_<number>_<var_name>
        # We want to strip off the prefix and just use the var_name
        k = k.split("_", 2)
        if len(k) == 3:
            k = k[2]
            global_vars[k] = v
    mod = compile_source_code(function_definition, global_vars)
    virtual_function = getattr(mod, "virtual_function")
    return virtual_function()


@library.filter
def debug_jinja(obj):
    stack = inspect.stack()
    def get_render_frame():
        for frame in stack:
            if frame.function == "render" and 'environment.py' in frame.filename:
                return frame
        return None
    frame = get_render_frame()
    assert frame is not None
    f_locals = frame.frame.f_locals
    template = f_locals["self"]
    context = f_locals["ctx"]  # noqa
    data = f_locals["kwargs"]  # noqa
    filters = template.environment.filters  # noqa
    breakpoint()
    return obj

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
        >>> encrypt_type9("123456")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
        >>> encrypt_type9("123456", "cvWdfQlRRDKq/U")
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