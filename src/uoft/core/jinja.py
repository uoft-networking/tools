from importlib.util import spec_from_file_location, module_from_spec
from base64 import b64encode
from pathlib import Path
import sys

from . import logging

try:
    from django_jinja.library import _local_env
except ImportError:
    # Global register dict for third party
    # template functions, filters and extensions.
    _local_env = {
        "globals": {},
        "tests": {},
        "filters": {},
        "extensions": set(),
    }

logger = logging.getLogger(__name__)


def _update_env(env):
    """
    Given a jinja environment, update it with third party
    collected environment extensions.
    """

    env.globals.update(_local_env["globals"])
    env.tests.update(_local_env["tests"])
    env.filters.update(_local_env["filters"])

    for extension in _local_env["extensions"]:
        env.add_extension(extension)


def _attach_function(attr, func, name=None):
    if name is None:
        name = func.__name__

    global _local_env
    _local_env[attr][name] = func
    return func


def _register_function(attr, name=None, fn=None):
    if name is None and fn is None:

        def dec(func):  # pyright: ignore[reportRedeclaration]
            return _attach_function(attr, func)

        return dec

    elif name is not None and fn is None:
        if callable(name):
            return _attach_function(attr, name)
        else:

            def dec(func):
                return _register_function(attr, name, func)

            return dec

    elif name is not None and fn is not None:
        return _attach_function(attr, fn, name)

    raise RuntimeError("Invalid parameters")


def extension(extension):
    global _local_env
    _local_env["extensions"].add(extension)
    return extension


def global_function(*args, **kwargs):
    return _register_function("globals", *args, **kwargs)


def test(*args, **kwargs):
    return _register_function("tests", *args, **kwargs)


def filter(*args, **kwargs):
    return _register_function("filters", *args, **kwargs)


def import_from_module(templates_dir: Path, module_name="filters", force=True):
    """
    Imports filters, tests, globals, and extensions from a module located within the template directory
    The module is expected to use the uoft.core.jinja decorators to register its filters, tests, globals, and extensions
    Returns True if the module was successfully imported, False if the module does not exist, and an ImportError if the
    module exists but has an error
    If force is set to False, the module will not be re-imported if it has already been imported
    """

    # As of this writing, there are 3 points of execution for this function:
    # 1. uoft.scripts.nautobot.lib.get_jinja_env, which is called by a uoft.scripts cli
    #    command and also by the test_render.py script in our tempaltes git repo
    # 2. uoft_nautobot.datasources.refresh_graphql_queries, which is called whenever a git
    #    repository is updated in nautobot
    # 3. uoft_nautobot.golden_config.get_django_env, which is called whenever a jinja
    #    template is rendered in nautobot golden config
    #    NOTE: in this usecase, force is set to False. We only want this entrypoint to
    #    import the filters module if it hasn't already been imported (ie on fresh boot of nautobot,
    #    if a Golden Config Compliance job is triggered *before* a Git Repository Sync job is triggered)
    def hash_path(template_dir: Path, module_name: str):
        """
        each module must have a unique valid python module name to insert into sys.modules,
        so we hash the path to the template directory and combine it with the module name to
        create a unique module name
        """
        hash_id = b64encode(str(template_dir).encode()).decode().replace("/", "").replace("+", "").replace("=", "")
        return "uoft_nautobot.jinja_" + module_name + "_" + hash_id

    module_file = templates_dir / (module_name + ".py")
    if not module_file.exists():
        logger.debug(f"No {module_name}.py found in {templates_dir}, skipping import")
        return False

    module_name = hash_path(templates_dir, module_name)
    if module_name in sys.modules:
        if not force:
            logger.debug(f"Module {module_name} already imported, skipping re-import")
            return True
        logger.debug(f"Module {module_name} already imported, re-importing to update filters")
        # Now you might think that just blindly re-importing an existing already-imported module
        # would be a bad idea, that it would cause problems with references to the old module still
        # sticking around in various places, and you'd be right. In this situation though, it's not really a problem.
        # no other data structures in the active python process are expected to contain references to the old module,
        # other than the `_local_env` dict, and it's expected that re-importing the modules will overwrite the entries
        # in that dict with the new functions from the re-imported module, so we should be fine.
        # in practice this may result in a very slow memory leak for long-running processes like nautobot, ie:
        #   when filters are removed from a new version of the module,
        #   references to them will not be removed from the _local_env dict,
        #   and if the module is re-imported enough times, we could end up
        #   with a large number of references to old versions of the filters in memory.
        #   in practice, this time of memory leak would take *months* to become a problem,
        #   and can easily be fixed by restarting the process.

    spec = spec_from_file_location(module_name, module_file)
    module = module_from_spec(spec)  # pyright: ignore[reportArgumentType]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # pyright: ignore[reportOptionalMemberAccess]
