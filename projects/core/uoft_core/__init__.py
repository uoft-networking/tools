# flake8: noqa

import inspect
import os
import pickle
import sys
import time
from shutil import which
from enum import Enum
from functools import cached_property
from getpass import getuser
from importlib.metadata import version
from pathlib import Path
from subprocess import CalledProcessError, run
from textwrap import dedent
from types import GenericAlias
from importlib.abc import Loader
from importlib.util import spec_from_file_location, spec_from_loader, module_from_spec
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    get_args,
    get_origin,
)


from pydantic import BaseSettings as PydanticBaseSettings, Extra, root_validator
from pydantic.fields import Field
import pydantic.types
from pydantic.main import ModelMetaclass

from . import logging
from .types import StrEnum, SecretStr
from . import toml
from ._vendor.decorator import decorate
from ._vendor.platformdirs import PlatformDirs

if TYPE_CHECKING:
    from pydantic import BaseModel

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
__version__ = version(__package__) # type: ignore

logger = logging.getLogger(__name__)
assert isinstance(logger, logging.UofTCoreLogger)

# region SECTION util functions & classes

F = TypeVar("F", bound=Callable)


def memoize(f: F) -> F:
    """
    A simple memoize implementation. It works by adding a .cache dictionary
    to the decorated function. The cache will grow indefinitely, so it is
    your responsibility to clear it, if needed.
    to clear: `memoized_function.cache = {}`
    """

    def _memoize(func, *args, **kw):
        key = (args, frozenset(kw.items())) if kw else args
        cache = func.cache  # attribute added by memoize
        if key not in cache:
            logger.trace(
                f"caching output of function `{func}` with arguments {args} and {kw}"
            )
            cache[key] = func(*args, **kw)
        return cache[key]

    f.cache = {}
    return decorate(f, _memoize)  # type: ignore


def debug_cache(func: F) -> F:
    """
    A function cache which persists to disk, but only when the `PYDEBUG` env var is set.
    All calls to functions decorated with this decorator will store the results of those functions in the cache,
    and that cache will be written to a file in the current directory called `.uoft_core.debug_cache.{function module + name}`.
    A utility function will be attached to the decorated function, and can be used to clear that function's cached results.

    Example:
        ```python
        # in a file called `my_script.py`
        from uoft_core import debug_cache
        @debug_cache
        def my_function():
            ...

        result = my_function() # my_function will run as normal and store its result in the cache
        result2 = my_function() # my_function will not run this time, instead, its cached result will be returned
        # at this point, there will be a file in your current directory called `.uoft_core.debug_cache.my_script.my_function`
        my_function.clear_cache() # the cache is now empty, and `.uoft_core.debug_cache.my_script.my_function` has been deleted
        result3 = my_function() # my_function will once again run as normal and store its result in the cache,
        # at this point, `.uoft_core.debug_cache.my_script.my_function` has been recreated
        ```

    """
    if not os.getenv("PYDEBUG"):
        logger.debug("PYDEBUG env var not set, debug_cache is disabled")
        return func
    fname = func.__qualname__
    fmodule = func.__module__
    if fmodule == "__main__":
        fmodule = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    file_name = f".uoft_core.debug_cache.{fmodule}.{fname}"
    try:
        with open(file_name, "rb") as f:
            cache: dict = pickle.load(f)
    except (IOError, ValueError):
        cache = {}

    def clear_cache():
        nonlocal cache
        cache = {}
        try:
            os.remove(file_name)
        except FileNotFoundError:
            pass

    def wrapped_func(*args, **kw):
        key = (args, frozenset(kw.items())) if kw else args
        if key not in cache:
            logger.trace(
                f"caching output of function `{fname}` with arguments {args} and {kw}"
            )
            cache[key] = func(*args, **kw)
            with open(file_name, "wb") as f:
                pickle.dump(cache, f)
        return cache[key]

    wrapped_func.clear_cache = clear_cache
    wrapped_func.__name__ = func.__name__
    wrapped_func.__doc__ = func.__doc__
    wrapped_func.__wrapped__ = func
    wrapped_func.__signature__ = inspect.signature(func)
    wrapped_func.__qualname__ = func.__qualname__
    # builtin functions like defaultdict.__setitem__ lack many attributes
    try:
        wrapped_func.__defaults__ = func.__defaults__
    except AttributeError:
        pass
    try:
        wrapped_func.__kwdefaults__ = func.__kwdefaults__
    except AttributeError:
        pass
    try:
        wrapped_func.__annotations__ = func.__annotations__
    except AttributeError:
        pass
    try:
        wrapped_func.__module__ = func.__module__
    except AttributeError:
        pass
    try:
        wrapped_func.__dict__.update(func.__dict__)
    except AttributeError:
        pass

    return wrapped_func  # type: ignore


def txt(s: str) -> str:
    """
    dedents a triple-quoted indented string, and strips the leading newline.
    Converts this:
    txt('''
        hello
        world
        ''')
    into this:
    "hello\nworld\n"
    """
    return dedent(s.lstrip("\n"))


def chomptxt(s: str) -> str:
    """
    dedents a triple-quoted indented string, and replaces all single newlines with spaces.
    replaces all double newlines (\n\n) with single newlines
    Converts this:
        txt('''
            hello
            world

            here's another
            line
            ''')
    into this:
    "hello world\nhere's another line"
    """
    res = dedent(s)
    res = res.replace("\n\n", "[PRESERVEDNEWLINE]")
    res = res.replace("\n", " ")
    res = res.replace("[PRESERVEDNEWLINE]", "\n")
    return res.strip()


def lst(s: str) -> List[str]:
    """
    convert a triple-quoted indented string into a list,
    stripping out '#' comments and empty lines
    Converts this:
    txt('''
        hello # comment in line

        # comment on its own
        world
        ''')
    into this:
    ['hello', 'world']
    """
    # dedent
    s = txt(s)
    # convert to list
    list_ = s.splitlines()
    # strip comments and surrounding whitespace
    list_ = [line.partition("#")[0].strip() for line in list_]
    # strip empty lines
    list_ = list(filter(bool, list_))
    return list_


def shell(cmd: str, input_: str | bytes | None = None, cwd: str | Path | None = None) -> str:
    """
    run a shell command, and return its output

    Optionally provide the shell command with input via the `input` argument.

    Example:
        >>> shell("grep -i 'hello'", "Hello world")
        'Hello world'
    """
    if input_ is not None and isinstance(input_, bytes):
        input_ = input_.decode()
    logger.trace(f"Running shell command: {cmd}")
    return (
        run(cmd, shell=True, capture_output=True, check=True, text=True, input=input_, cwd=cwd)
        .stdout
        .strip()
    )


class DataFileFormats(str, Enum):
    ini = "ini"
    json = "json"
    toml = "toml"
    yaml = "yaml"


def parse_config_file(file: Path, parse_as: Optional[DataFileFormats] = None):
    obj: Dict[str, Any]
    content = file.read_text()
    if parse_as:
        file_format = "." + parse_as.value
    else:
        file_format = file.suffix
    if file_format == ".ini":
        import configparser  # noqa

        cfp = configparser.ConfigParser()
        cfp.read_string(content)
        obj = dict(cfp["_common_"])
        for sect in cfp.sections():
            if sect != "_common_":
                obj[sect] = dict(cfp[sect])
    elif file_format == ".json":
        import json  # noqa

        obj = dict(json.loads(content))
    elif file_format == ".toml":
        from . import toml

        obj = dict(toml.loads(content))
    elif file_format == ".yaml":
        from . import yaml

        obj = dict(yaml.loads(content))
    else:
        raise UofTCoreError(
            chomptxt(
                f"""Failed to parse {file}. 
                Config file type {file_format} not supported.
                Only .ini, .json, .toml, and .yaml files are supported"""
            )
        )
    return obj


def write_config_file(
    file: Path, obj: dict[str, Any], write_as: Optional[DataFileFormats] = None
):
    file.parent.mkdir(parents=True, exist_ok=True)
    if write_as:
        file_format = "." + write_as.value
    else:
        file_format = file.suffix
    if file_format == ".ini":
        import configparser  # noqa

        cfp = configparser.ConfigParser()
        for k, v in obj.items():
            # this implementation is fragile and likely to break, but it's good enough for now
            cfp[k] = v
            cfp.write(file.open("w"))
    elif file_format == ".json":
        import json  # noqa

        file.write_text(json.dumps(obj, indent=4))
    elif file_format == ".toml":
        from . import toml

        file.write_text(toml.dumps(obj))
    elif file_format == ".yaml":
        from . import yaml

        file.write_text(yaml.dumps(obj))
    else:
        raise UofTCoreError(
            chomptxt(
                f"""Failed to parse {file}. 
                Config file type {file_format} not supported.
                Only .ini, .json, .toml, and .yaml files are supported"""
            )
        )


def create_or_update_config_file(
    file: Path, obj: dict[str, Any], write_as: Optional[DataFileFormats] = None
):
    if file.exists():
        logger.debug(f"Updating existing config file {file}")
        existing = parse_config_file(file, parse_as=write_as)
        existing.update(obj)
        obj = existing
    else:
        logger.debug(f"Creating new config file {file}")
    write_config_file(file, obj, write_as=write_as)

_pass_cmd = os.environ.get("PASS_CMD", "pass")
_pass_installed = None
def _is_pass_installed():
    global _pass_installed
    if _pass_installed is None:
        _pass_installed = bool(which("pass"))
    return _pass_installed

# dynamically inheriting from the cls of Path is an unfortunate necessity
# otherwise we would have to manually create *two* PassPath classes, one for
# linux/mac and one for windows, and then dynamically set which one would be 
# *the* PassPath class at runtime. inheriting from `type(Path())` seems like 
# the lesser of two evils
class PassPath(type(Path())):
    """An abstract path representing an entry in the `pass` password store"""

    _contents: str | None

    def __new__(cls, *args):
        self = super().__new__(cls, *args)
        self._contents = None
        return self

    @property
    def command_name(self) -> str:
        return f"{_pass_cmd} show {self}"

    @property
    def contents(self) -> str:
        if not _is_pass_installed():
            logger.debug(f"{_pass_cmd} is not installed, skipping {self}")
            return ""
        if self._contents is None:
            try:
                logger.debug(f"Running pass command: `{self.command_name}`")
                self._contents = shell(self.command_name)
            except CalledProcessError as e:
                if 'gpg: decryption failed:' in e.stderr:
                    logger.error(e.stderr)
                    raise UofTCoreError("Failed to decrypt password-store entry. Check your GPG keys") from e
                if e.returncode == 1:
                    logger.debug(f"Password-store entry {self} does not exist, skipping")
                self._contents = ""
        return self._contents

    def exists(self) -> bool:
        if not _is_pass_installed():
            return False
        return bool(self.contents)

    def mkdir(
        self, mode: int = 0, parents: bool = False, exist_ok: bool = True
    ) -> None:
        # mkdir doesn't make sense in the context of pass,
        # so we'll stub it out and pretend it succeeded
        return None

    def read_text(self, encoding: str | None = None, errors: str | None = None) -> str:
        return self.contents

    def write_text(
        self, data: str, encoding: str | None = None, errors: str | None = None
    ) -> None:
        if _is_pass_installed():
            shell(f"{_pass_cmd} insert -m {self}", input_=data)
            self._contents = data
        else:
            raise UofTCoreError(
                chomptxt(
                    f"""Failed to write to {self}. 
                    pass is not installed"""
                )
            )


def bitwarden_unlock(password_file: Path | None = None):
    if os.environ.get("BW_SESSION"):
        # vault is already unlocked, nothing to see here
        return
    cmd = "bw unlock --raw"
    if not password_file:
        password_file = Path.home() / ".bw_pass"
    # raise a warning if password file access mode is not 600
    if password_file.exists():
        # fancy bitwise AND to pull out just the permission bits and compare
        if password_file.stat().st_mode & 0o777 != 0o600:
            logger.warning(
                f"Password file {password_file} has insecure permissions. Please set it to 600"
            )
    else:
        logger.info(f"Password file {password_file} not found, skipping")
    if password_file:
        cmd += f" --password-file {password_file}"
    session = shell(cmd)

    # inject the session into the environment
    os.environ["BW_SESSION"] = session


def bitwarden_get(secret_name: str) -> str:
    # this function may get called once or many times, depending on how many secrets are referenced in other config files
    # when called, this function needs to unlock the bitwarden vault if it hasn't already been unlocked, and then fetch the secret
    bitwarden_unlock()
    return shell(f"bw get item {secret_name} --raw")

class Timeit:
    """
    Wall-clock timer for performance profiling. makes it really easy to see
    elapsed real time between two points of execution.

    Example:
        ```python
        from uoft_core import Timeit

        # the clock starts as soon as the class is initialized
        timer = Timeit()
        time.sleep(1.1)
        timer.interval() # record an interval
        assert timer.float == 1.1
        assert timer.str == '1.1000s'
        time.sleep(2.5)
        timer.interval()

        # only the time elapsed since the start
        # of the last interval is recorded
        assert timer.float == 2.5
        assert timer.str == '2.5000s'

        # timer.interval() is the same as timer.stop() except it starts a new
        # clock immediately after recording runtime for the previous clock
        time.sleep(1.5)
        timer.stop()
        ```

    """

    def __init__(self) -> None:
        self.time = self.now
        self.start = self.time
        self.float = 0.0

    @classmethod
    def time_this(cls, func: Callable):
        def wrapper(*args, **kwargs):
            t = Timeit()
            res = func(*args, **kwargs)
            print(f"{func.__name__} completed in {t.stop().str}")
            return res

        return wrapper

    @property
    def now(self):
        return time.perf_counter()

    @property
    def str(self):
        return f"{self.float:.4f}s"

    def stop(self):
        self.float = self.now - self.time
        return self

    def interval(self):
        self.stop()
        self.time = self.now
        return self

    @property
    def total(self):
        total = self.now - self.start
        return f"{total:.4f}s"


def create_python_module(module_name, source: types.Path | str, globals_=None):
    class VirtualSourceLoader(Loader):
        def __init__(self, source_code):
            self.source = source_code

        def exec_module(self, module) -> None:
            exec(self.source, module.__dict__)  # pylint: disable=exec-used

    if isinstance(source, types.Path):
        spec = spec_from_file_location(module_name, source)
    else:
        spec = spec_from_loader(module_name, VirtualSourceLoader(source))
    assert spec is not None
    module = module_from_spec(spec)
    if globals_ is not None:
        assert isinstance(globals_, dict), "globals_ must be a dict"
        module.__dict__.update(globals_)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return sys.modules[module_name]


def compile_source_code(source_code, globals_=None):
    module_name = f"<virtual_module#{hash(source_code)}>"
    module = create_python_module(module_name, source_code, globals_)
    return module


class UofTCoreError(Exception):
    pass

# endregion !SECTION util functions & classes

# region types


class File(StrEnum):
    writable = object()
    readable = object()
    creatable = object()
    unusable = object()

    @classmethod
    def is_writable(cls, f: Path):
        return os.access(f, os.W_OK)

    @classmethod
    def is_readable(cls, f: Path):
        return os.access(f, os.R_OK)

    @classmethod
    def is_creatable(cls, f: Path):
        # a file is createable if it doesn't exist and its parent directory is writable / creatable
        try:
            return (not f.exists()) and (
                cls.is_writable(f.parent) or cls.is_creatable(f.parent)
            )
        except PermissionError:
            # f.exists() will fail if we don't have execute permission on the file's parent folder.
            # when this happens, the file should be deemed uncreatable
            return False

    @classmethod
    def state(cls, f: Path):
        if cls.is_writable(f):
            return cls.writable
        elif cls.is_readable(f):
            return cls.readable
        elif cls.is_creatable(f):
            return cls.creatable
        else:
            return cls.unusable


# endregion types


class Util:
    """
    Core class for CLI apps to simplify access to config files, cache directories, and logging configuration
    """

    app_name: str
    config: "Util.Config"

    class Config:
        """
        Container class for all functionality related to retrieving and working with configuration data
        """

        parent: "Util"
        common_user_config_dir: Path

        def __init__(self, parent: "Util") -> None:
            self.parent = parent
            self.common_user_config_dir = Path.home() / ".config/uoft-tools"

        def dirs_generator(self):
            """generate a list of folders in which to look for config files

            Yields:
                Path: config file directories, yielded in order of priority from high to low

            Note:
                config files from high-priority directory should be selected first.
                priority list (low to high):
                - default os-specific site config folder (/etc/xdg/uoft-tools/ on Linux, /Library/Application Support/uoft-tools/ on OSX, etc)
                - directory pointed to by {self.app_name}_SITE_CONFIG environment variable if set
                - cross-platform user config folder (~/.config/uoft-tools/ on all operating systems)
                - default os-specific user config folder (~/.config/at_utils on Linux, ~/Library/Application Support/uoft-tools/ on OSX, etc)
                - directory pointed to by {self.app_name}_USER_CONFIG environment variable if set

            """
            # Site dirs
            if custom_site_config := self.parent.get_env_var("site_config"):
                logger.trace(f"Using {custom_site_config} as site config directory")
                yield Path(custom_site_config)
            else:
                yield self.parent.dirs.site_config_path

            # User dirs
            yield self.common_user_config_dir

            if custom_user_config := self.parent.get_env_var("user_config"):
                logger.trace(f"Using {custom_user_config} as user config directory")
                yield Path(custom_user_config)
            elif (
                user_config := self.parent.dirs.user_config_path
            ) != self.common_user_config_dir:
                # yield user_config, but only if it's different than cross-platform user config
                # if you're on linux, these two will be the same. no sense yielding the same path twice
                yield user_config

        def files_generator(self):
            """
            Generates a set of config files that may or may not exist,
            in descending order (from lowest to highest priority).

            Example:
                given self.app_name = example,
                and os = MacOS,
                and user = 'alex'
                this method would yield the following:

                - (PosixPath('/Library/Preferences/uoft-tools/shared.ini'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/shared.yaml'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/shared.json'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/shared.toml'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/example.ini'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/example.yaml'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/example.json'), File.unusable)
                - (PosixPath('/Library/Preferences/uoft-tools/example.toml'), File.unusable)
                - (PosixPath('/Users/alex/.config/uoft-tools/shared.ini'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/shared.yaml'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/shared.json'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/shared.toml'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/example.ini'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/example.yaml'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/example.json'), File.creatable)
                - (PosixPath('/Users/alex/.config/uoft-tools/example.toml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/shared.ini'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/shared.yaml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/shared.json'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/shared.toml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/example.ini'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/example.yaml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/example.json'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/uoft-tools/example.toml'), File.creatable)

            """

            def file_names():
                for basename in ["shared", self.parent.app_name]:
                    for ext in ["ini", "yaml", "json", "toml"]:
                        yield f"{basename}.{ext}"

            for directory in self.dirs_generator():
                for name in file_names():
                    file = directory / name
                    yield file, File.state(file)

        @cached_property
        def files(self):
            res = list(self.files_generator())
            logger.trace(f"Caching list of config files: {res}")
            return res

        @property
        def readable_files(self):
            return [
                file
                for file, state in self.files
                if state in [File.readable, File.writable]
            ]

        @property
        def writable_files(self):
            return [file for file, state in self.files if state == File.writable]

        @property
        def writable_or_creatable_files(self):
            return [
                file
                for file, state in self.files
                if state in [File.writable, File.creatable]
            ]

        def get_file_or_fail(self):
            """
            Find a valid config file.
            File can be stored in a site-wide directory (ex. /etc/xdg/uoft-tools)
            or a user-local directory (ex. ~/.config/uoft-tools)
            File must have basename matching either the `app_name` attribute of this class, or the word "shared"
            File must have one of the following extensions: ['.ini', '.yaml', '.json', '.toml']
            If an environment variable like {self.app_name}_CONFIG_FILE exists and points
            to a file that exists, that file will be returned instead of any file in any of the above directories.

            Raises:
                AtUtilsError: if no valid config file found
            """
            if custom_config_file := self.parent.get_env_var("config_file"):
                logger.trace(
                    f"Skipping normal config file lookup, using {custom_config_file} as configuration file"
                )
                return Path(custom_config_file)
            # else:
            try:
                # self.readable_config_files lists files from lowest priority to highest.
                # Since we're only fetching one file (not merging),
                # we want to grab the highest-priority file only.
                files = self.readable_files
                last_file = files[-1]
                logger.trace(
                    f"selecting config file {last_file} from available config files {files}"
                )
                return last_file
            except IndexError:
                raise UofTCoreError(  # pylint: disable=raise-missing-from
                    chomptxt(
                        f"""
                    Could not find a valid config file for application {self.parent.app_name} 
                    from any of: {[f for f, _ in self.files]}
                    """
                    )
                )

        @cached_property
        def merged_data(self) -> Dict[str, Any]:
            data = {}
            files = self.readable_files
            if custom_config_file := self.parent.get_env_var("config_file"):
                logger.trace(
                    f"Adding {custom_config_file} to list of config files to load"
                )
                files.append(Path(custom_config_file))
            if not files:
                raise UofTCoreError(
                    chomptxt(
                        f"""
                    Could not find a valid config file for application {self.parent.app_name} 
                    from any of: {[f for f, _ in self.files]}
                    """
                    )
                )
            for file in files:
                logger.debug(f"Loading config data from {file}")
                data.update(parse_config_file(file))
            return data

        def get_key_or_fail(self, key: str):
            """
            simple method to get a value from the config file for a given key

            Args:
                key: top-level key to retrieve from a parsed dictionary loaded from config file

            Raises:
                KeyError: if the given key couldn't be found in the config file
                AtUtilsError: any exception raised by self.merged_data
            """
            if custom_key := self.parent.get_env_var(key):
                logger.trace(
                    f"Found environment variable override for config option {key}, using its value instead of pulling from config file"
                )
                return custom_key
            # else:
            obj = self.merged_data

            val = obj.get(key)
            if not val:
                raise KeyError(f"Could not find key {key} in config object {obj}")

            logger.debug(f"Found key {key} in config object")
            return val

        def get_data_from_model(self, model: Type["BaseModel"]):
            "using the fields of a pydantic data model as keys, fetch values for those keys from config files and environment variables and return a dict"
            conf = self.merged_data
            for field, field_info in model.__fields__.items():
                if field not in conf:
                    # merged_config_data only includes data from config files, not env vars.
                    if (env_var := self.parent.get_env_var(field)) is None:
                        # if the field has a default value, this is fine.
                        if field_info.required:
                            raise Exception(
                                f"Configuration option `{field}` is required and unset"
                            )
                        else:
                            continue
                    conf[field] = env_var
            return conf

    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self.dirs: PlatformDirs = PlatformDirs("uoft-tools")
        self.config: "Util.Config" = self.Config(self)
        # there should be one config path which is common to all OS platforms,
        # so that users who sync configs between multiple computers can sync
        # those configs to the same directory across machines and have it *just work*
        # By convention, this path is ~/.config/uoft-tools

    # region util
    def get_env_var(self, property_):
        "fetches a namespaced environment variable"
        property_ = property_.replace("-", "_").replace(
            ".", "_"
        )  # property names must have underscores, not dashes or dots
        env_var_name = f"{self.app_name}_{property_}".upper()
        res = os.environ.get(env_var_name)
        msg = f"Environment variable '{env_var_name}' for property '{property_}'"
        if res:
            logger.trace(f"{msg} is set to '{res}'")
        else:
            logger.trace(f"{msg} is not set")
        return res

    def _clear_caches(self):
        try:
            del self.config.files
        except AttributeError:
            pass
        try:
            del self.config.merged_data
        except AttributeError:
            pass

    # endregion util
    # region config

    # endregion config
    # region cache

    @property
    def cache_dir(self):
        """
        Fetches the site-wide cache directory for {self.app_name} if available
        or the user-local cache directory for {self.app_name} as a fall-back.
        If a given directory does not exist but can be created, it will be created and returned.
        If an environment variable like {self.app_name}_SITE_CACHE exists and points
        to a directory that exists, that directory will be returned.
        If an environment variable like {self.app_name}_USER_CACHE exists and points
        to a directory that exists, and no valid site-wide cache directory was found,
        that directory will be returned.
        """

        # Site dir
        site_cache = self.dirs.site_data_path.joinpath(self.app_name)
        if custom_site_cache := self.get_env_var("site_cache"):
            logger.trace(f"using {custom_site_cache} as site cache directory")
            return Path(custom_site_cache)
        # else:
        try:
            site_cache.mkdir(parents=True, exist_ok=True)
            return site_cache
        except OSError:
            pass

        # User dir
        user_cache = self.dirs.user_cache_path.joinpath(self.app_name)
        if custom_user_cache := self.get_env_var("user_cache"):
            logger.trace(f"using {custom_user_cache} as user cache directory")
            return Path(custom_user_cache)
        # else:
        try:
            user_cache.mkdir(parents=True, exist_ok=True)
            return user_cache
        except OSError:
            raise UofTCoreError(  # pylint: disable=raise-missing-from
                chomptxt(
                    f"""
                Neither site-wide cache directory ({site_cache}) nor 
                user-local cache directory ({user_cache}) exists, 
                and neither directory can be created.
                """
                )
            )

    @property
    def history_cache(self) -> Path:
        history = self.cache_dir.joinpath("history")
        history.mkdir(parents=True, exist_ok=True)
        return history

    # endregion cache


S = TypeVar("S", bound="BaseSettings")
F = TypeVar("F", bound=Callable)


class BaseSettingsMeta(ModelMetaclass):
    # This metaclass is responsible for setting the env_prefix attribute on the Config class of any 
    # subclass of BaseSettings
    def __new__(cls, name, bases, namespace, **kwargs):
        config_class = namespace.get("Config")
        if config_class is None:
            # This may be a subclass of a class that defines Config
            for base in bases:
                if hasattr(base, "Config"):
                    config_class = base.Config
                    break
        if (app_name := config_class.app_name) is not None:
            # BaseSettings.__init_subclasses__ ensures that app_name is set
            # So the only class that this will be None for is BaseSettings itself
            config_class.env_prefix = f"UOFT_{app_name.upper()}_"
        return super().__new__(cls, name, bases, namespace, **kwargs)


class BaseSettings(PydanticBaseSettings, metaclass=BaseSettingsMeta):
    _instance = None  # type: ignore

    @classmethod
    def _update_cache_instance(cls, *args, **kwargs):
        cls._instance = cls(*args, **kwargs)  # type: ignore

    @classmethod
    def from_cache(cls: Type[S]) -> S:
        # For each subclass of BaseSettings, this method should return an instance of that subclass
        with logging.Context(f'Settings(app_name={cls.Config.app_name})'):
            if cls._instance is None:
                    logger.debug("Loading settings")
                    cls._instance = cls()
            else:
                logger.debug("Settings already loaded")
            cls._instance: S
            return cls._instance

    def __init_subclass__(cls, **kwargs):
        app_name = getattr(cls.Config, "app_name", None)
        if app_name is None:
            raise TypeError(
                "Subclasses of BaseSettings must include a Config class with an app_name attribute"
            )
        if not issubclass(cls.Config, BaseSettings.Config):
            raise TypeError(
                "Subclasses of BaseSettings must include a Config class that is a subclass of BaseSettings.Config"
            )
        super().__init_subclass__(**kwargs)

    @pydantic.validator("*", pre=True)
    def _validate_ref_fields(cls, value):
        # if any field has a value that looks like "ref[prefix:field]", 
        # verify that prefix is either `pass` (for the linux password-store) or `bw` (for bitwarden)
        # look up 'field' in the password store or bitwarden and replace the value with the result
        if isinstance(value, str) and value.startswith("ref[") and value.endswith(']'):
            logger.debug(f"Found reference field: {value}")
            ref = value[4:-1]
            if not ref:
                raise ValueError("Reference field cannot be empty")
            if ref.startswith("pass:"):
                lookup_name = ref[5:]
                return PassPath(lookup_name).contents
            if ref.startswith("bw:"):
                lookup_name = ref[3:]
                return bitwarden_get(lookup_name)
            raise ValueError(f"Invalid reference field: {value}")
        return value

    @classmethod
    def _util(cls) -> "Util":
        return Util(cls.__config__.app_name)

    @property
    def util(self):
        return self._util()

    @classmethod
    def wrap_typer_command(cls, func: F) -> F:
        # Here we import typer outside top-level scope because it only makes sense to import it
        # when we're running in a typer app, which is the only situation where this method is used.
        import typer  # pylint: disable=import-outside-toplevel
        sig = inspect.signature(func)
        settings_parameters = []
        for field_name, field in cls.__fields__.items():
            finfo = field.field_info
            if finfo.title and finfo.description:
                help_ = f"{finfo.title}: {finfo.description}"
            elif finfo.title:
                help_ = finfo.title
            elif finfo.description:
                help_ = finfo.description
            else:
                help_ = None

            parser=None
            if field.outer_type_ in [SecretStr, pydantic.types.SecretStr]:
                type_ = SecretStr
                parser = SecretStr
            elif get_origin(field.outer_type_) is dict:
                type_ = List[str]
                help_ += " (key value pairs separated by =)"
                def parse_key_value(value):
                    try:
                        k, v = value.split("=", 1)
                    except ValueError:
                        raise ValueError("Key value pairs must be separated by =")
                    return k, v
                parser = parse_key_value
            else:
                type_ = field.outer_type_
            option = typer.Option(default=None, help=help_, parser=parser)
            param = inspect.Parameter(
                field_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=option,
                annotation=Optional[type_],
            )
            settings_parameters.append(param)
        parameters = settings_parameters + list(sig.parameters.values())
        new_sig = sig.replace(parameters=parameters)
        func.__signature__ = new_sig
        func.settings_parameters = settings_parameters

        # here we return the original function, but with the new signature,
        # and let the original function handle the settings-related arguments passed in by typer,
        # but we may want to wrap it in another function which pulls out and handles the
        # settings-related arguments first and then calls the original function...
        def _wrapper(f, *args):
            # we need to pull out the settings-related arguments from the args list
            # and pass them to the settings function
            settings_kwargs = {}
            for param, value in zip(func.settings_parameters, args):
                if value is None:
                    continue
                # some dirty hacks to get around quirks in typer behaviour
                inner_type = get_args(param.annotation)[0]
                if type(inner_type) is GenericAlias:
                    inner_type = get_origin(inner_type)
                if inner_type is list and value == []:
                    continue
                if inner_type is bool and value == False:
                    continue
                settings_kwargs[param.name] = value

            if settings_kwargs:
                cls._update_cache_instance(
                    **settings_kwargs
                )  # pylint: disable=protected-access
            number_of_settings_args = len(func.settings_parameters)
            new_args = args[number_of_settings_args:]
            return f(*new_args)

        return decorate(func, _wrapper)  # type: ignore

    @classmethod
    def _prompt(cls):
        return Prompt(cls._util().history_cache)

    @property
    def prompt(self):
        return self._prompt()

    @root_validator(pre=True)
    @classmethod
    def prompt_for_missing_values(cls, values):
        missing_keys = [key for key in cls.__fields__ if key not in values]
        logger.debug(f"Missing keys: {missing_keys}")

        # If a BaseSettings subclass appears in the missing_keys list, and that field is marked prompt=False,
        # Then we should source the value from the subclass's from_cache method, and remove the subclass from the missing_keys list
        # Additionally, if a field marked prompt=False is missing, and that field has a default value, we should use the default value
        for key in missing_keys[:]:
            field = cls.__fields__[key]
            type_ = get_origin(field.outer_type_)
            if type_ is None:
                type_ = field.outer_type_
            try:
                is_model = issubclass(type_, BaseSettings)
            except TypeError:
                is_model = False
            if field.field_info.extra.get("prompt", True) is False:
                logger.debug(f"Prompting disabled for field {key}")
                if is_model:
                    values[key] = type_.from_cache()
                
                if field.required is False:
                    values[key] = field.default
                missing_keys.remove(key)


        if not missing_keys:
            # Everything's present and accounted for. nothing to do here
            logger.debug("No missing keys remaining to prompt for")
            return values

        if not cls.Config.prompt_on_missing_values:
            # interactively prompting for values is disabled on this subclass
            # Return values as is and let pydantic report validation errors on missing fields
            logger.debug("Prompting disabled for missing values")
            return values

        if not sys.stdout.isatty():
            # We're not in a terminal.  We can't prompt for input.
            # Return values as is and let pydantic report validation errors on missing fields
            logger.debug("Not in a terminal. Skipping interactive prompt for missing values")
            return values

        # We're in a terminal and we're missing some values.
        p = cls._prompt()
        for key in missing_keys:
            field = cls.__fields__[key]
            values[key] = p.from_model_field(key, field)

        cls._interactive_save_config(values)

        return values

    @classmethod
    def _interactive_save_config(cls, values):
        # get list of valid save targets
        # including from pass
        save_targets = [
            f"[password-store] uoft-{cls.__config__.app_name}",
            f"[password-store] shared/uoft-{cls.__config__.app_name}",
        ]
        for file_path, file_state in cls._util().config.files:
            if file_state in {File.writable, File.creatable}:
                save_targets.append(str(file_path))
        logger.debug(f"Save targets: {save_targets}")

        # prompt user to select a save target
        p = cls._prompt()
        try:
            save_target = p.get_from_choices(
                "Save settings to",
                save_targets,
                "Select a target to save configuration settings to. Press ctrl-c or ctrl-d to skip saving.",
            )

            # save to selected target
            if "[password-store]" in save_target:
                secret_name = save_target.split("] ")[1]
                path = PassPath(secret_name)
                write_as = DataFileFormats.toml
            else:
                path = Path(save_target)
                write_as = None

            create_or_update_config_file(path, values, write_as=write_as)
        except (KeyboardInterrupt, EOFError):
            pass

    def interactive_save_config(self):
        # _interactive_save_config is a class method, but we want to call it on an instance
        # after instance values have been updated. 
        # One unfortunate side-effect of triggering _interactive_save_config from an instance method
        # as opposed to a pydantic validator, is that `SecretStr` fields cannot be directly serialized. 
        # they get treated as strings, serialized as "*************", and then the original actual value is lost.

        from collections.abc import Mapping, Iterable

        # to prevent this, we-ll need to recursively walk the model and replace SecretStr fields with their actual values
        values = self.dict()
        def _walk(d):
            if isinstance(d, Mapping):
                for k, v in d.items():
                    if isinstance(v, SecretStr):
                        d[k] = v.get_secret_value()
                    elif isinstance(v, (Mapping, Iterable)):
                        _walk(v)
            elif isinstance(d, Iterable) and not isinstance(d, str):
                for i in d:
                    _walk(i)
        _walk(values)
        self.__class__._interactive_save_config(values)

    class Config(PydanticBaseSettings.Config):
        env_file = ".env"
        app_name: str = None  # type: ignore
        prompt_on_missing_values = True
        extra = Extra.allow

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return (
                init_settings,
                env_settings,
                file_secret_settings,
                cls.pass_settings_source(),
                cls.config_file_settings,
            )

        @classmethod
        def pass_settings_source(cls):
            app_name = cls.app_name

            def settings_from_pass(settings: "BaseSettings"):
                res = {}
                for name in [f"uoft-{app_name}", f"shared/uoft-{app_name}"]:
                    path = PassPath(name)
                    try:
                        text = path.read_text()
                        if not text:
                            # if pass is not installed, or if the pass entry doesn't exist, that's not necessarily an error.
                            continue
                        logger.debug(f"Successfully decrypted and loaded content from {path}, attempting to parse as TOML data")
                        res.update(toml.loads(text))
                        logger.debug(f"TOML data parse OK from {path}")
                    except toml.TOMLDecodeError as e:
                        # at this point, we can be sure that pass is installed, and the user did create a pass entry,
                        # but the entry is not valid TOML. This case IS an error and should be bubbled up to the user.
                        raise UofTCoreError(
                            f"Error parsing data returned from `{path.command_name}`. expected a TOML document, but failed parsing as TOML: {e.args}"
                        ) from e
                    logger.info(f"Successfully loaded settings from {path}")
                return res

            return settings_from_pass

        @staticmethod
        def config_file_settings(settings: "BaseSettings"):
            try:
                cfg = settings.util.config
                return cfg.merged_data
            except UofTCoreError:
                # If no config files exist, that may not necessarily be an error.
                # We'll let pydantic check all settings sources and determine if a given setting is missing
                return {}

    __config__: ClassVar[Type[Config]]

