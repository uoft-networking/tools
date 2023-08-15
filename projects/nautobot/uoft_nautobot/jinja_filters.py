from textwrap import indent, dedent
from typing import Literal
from hashlib import shake_128
from django_jinja import library
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader
from . import Settings
from .golden_config import encrypt_type9, type9_encode
from pathlib import Path
import sys
from importlib.util import spec_from_file_location, module_from_spec
from base64 import b64encode
import inspect

# At import time, we need to import filters defined in git repositories
def _hash_path(path: Path):
    """Converts a path to a unique-ish valid python identifier / module name"""
    return b64encode(path.stem.encode()).decode().replace("/", "").replace("+", "").replace("=", "")

def _import_repo_filters_module(repo_path: Path):
    module_name = "uoft_nautobot.jinja_filters.from_git_repo_" + _hash_path(repo_path)
    module_file = repo_path / "filters.py"
    if not module_file.exists():
        # Skip if this repo doesn't have a filters.py
        return None
    if module_name in sys.modules:
        # Skip if this module has already been imported
        return sys.modules[module_name]
    spec = spec_from_file_location(module_name, module_file)
    module = module_from_spec(spec) # type: ignore
    sys.modules[module_name] = module
    spec.loader.exec_module(module) # type: ignore
    return module

from django.conf import settings
for repo in Path(settings.GIT_ROOT).iterdir():
    if repo.is_dir():
        _import_repo_filters_module(repo)

def _get_jinja_env() -> SandboxedEnvironment:
    """
    nautobot-nornir, nautobot-golden-config, and nautobot-netbox-importer all use a
    separate jinja environment from the one used by django_jinja
    This function finds the jinja environment being used to render the current template
    """
    for frame in inspect.stack():
        if frame.function == "load":
            vars = frame.frame.f_locals
            if 'environment' not in vars:
                continue
            return vars['environment']
    raise RuntimeError("Unable to find the template being rendered")

@library.filter
def load_local_jinja_library(_):
    """Loads filters, tests, globals, and extensions collocated with the template being rendered"""

    environment = _get_jinja_env()
    loader: FileSystemLoader = environment.loader  # type: ignore
    repo = Path(loader.searchpath[0])
    _import_repo_filters_module(repo)

    # The imported filters module is expected to register its own filters, tests, globals, and extensions
    # using the django_jinja.library decorators
    # We need to re-register them with the current environment
    library._update_env(environment)

    # TODO: remove this hack
    environment.trim_blocks = True
    environment.lstrip_blocks = True

    # because this is a filter, we need to return something,
    # something that won't show up in the rendered output
    return ""

@library.filter
def config_path(obj):
    "returns an ideal file path to store the rendered/backed-up config for a given object"
    folder_name = "device-location-missing"
    if obj.location:
        if obj.location.location_type.slug == "building":
            folder_name = obj.location.slug
        else:
            folder_name = obj.location.parent.slug
    ext = "txt"
    if obj.platform:
        match obj.platform.slug:
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
    s = Settings.from_cache()
    if password_variant == 'enable':
        password = s.ssh.enable_secret.get_secret_value()
    elif password_variant == 'admin':
        password = s.ssh.admin.password.get_secret_value()
    else:
        raise ValueError(f"Invalid password variant: {password_variant}")

    # convert variable-length switch name to 14 bytes of cisco-compatible salt
    salt = type9_encode(shake_128(hostname.encode()).digest(14))[:14]
    return encrypt_type9(password, salt=salt)


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
