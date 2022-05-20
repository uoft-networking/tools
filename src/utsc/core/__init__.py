# flake8: noqa

import os, sys, time, logging, logging.handlers, re, platform
from pathlib import Path
from functools import cached_property
from enum import Enum
from typing import Dict, List, Any, Optional, Type, TYPE_CHECKING
from textwrap import dedent
from getpass import getuser
from subprocess import run
from importlib.metadata import version

from loguru import logger
from rich.console import Console
from utsc.core._vendor.platformdirs import PlatformDirs
from ._vendor.decorator import decorate

if TYPE_CHECKING:
    from loguru import Message
    from pydantic import BaseModel

__version__ = version(__package__)

logger.disable(__name__)
# loguru best practice is for libraries to disable themselves and
# for cli apps to re-enable logging on the libraries they use

# region SECTION util functions & classes
def memoize(f):
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
    return decorate(f, _memoize)


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
    replaces all double newlines (\\n\\n) with single newlines
    Converts this:
    txt('''
        hello
        world

        here's another
        line
        ''')
    into this:
    "hello world\\nhere's another line"
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


def shell(cmd: str) -> str:
    return run(cmd, shell=True, capture_output=True, check=True).stdout.decode().strip()


class DataFileFormats(str, Enum):
    ini = "ini"
    json = "json"
    toml = "toml"
    yaml = "yaml"

def parse_config_file(file: Path, parse_as: Optional[DataFileFormats] = None):
    obj: Dict[str, Any]
    content = file.read_text()
    if parse_as:
        file_format = '.' + parse_as.value
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
        raise UTSCCoreError(
            chomptxt(
                f"""Failed to parse {file}. 
                Config file type {file_format} not supported.
                Only .ini, .json, .toml, and .yaml files are supported"""
            )
        )
    return obj


def write_config_file(file: Path, obj: dict[str, Any], write_as: Optional[DataFileFormats] = None):
    file.parent.mkdir(parents=True, exist_ok=True)
    if write_as:
        file_format = '.' + write_as.value
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
        raise UTSCCoreError(
            chomptxt(
                f"""Failed to parse {file}. 
                Config file type {file_format} not supported.
                Only .ini, .json, .toml, and .yaml files are supported"""
            )
        )


class Timeit:
    """
    Wall-clock timer for performance profiling. makes it really easy to see
    elapsed real time between two points of execution.

    Example:
        from at_utils.main import Timeit

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


    """

    def __init__(self) -> None:
        self.start = time.perf_counter()

    def stop(self):
        self.now = time.perf_counter()
        self.float = self.now - self.start
        self.str = f"{self.float:.4f}s"
        return self

    def interval(self):
        self.stop()
        self.start = self.now
        return self


class UTSCCoreError(Exception):
    pass


class InterceptHandler(logging.Handler):
    "This handler, when attached to the root logger of the python logging module, will forward all logs to Loguru's logger"

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# endregion !SECTION util functions & classes

# region types
class StrEnum(str, Enum):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self) -> str:
        return self.name

    @property
    def str(self):
        return self.__str__()

    @classmethod
    def from_str(cls, string):
        for member in cls:
            if str(member) == string:
                return member


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
    dirs: PlatformDirs
    console: Console
    logging: "Util.Logging"
    config: "Util.Config"

    class Config:
        """
        Container class for all functionality related to retrieving and working with configuration data
        """

        parent: "Util"
        common_user_config_dir: Path

        def __init__(self, parent: "Util") -> None:
            self.parent = parent
            self.common_user_config_dir = Path.home() / ".config/utsc-tools"

        def dirs_generator(self):
            """generate a list of folders in which to look for config files

            Yields:
                Path: config file directories, yielded in order of priority from high to low

            Note:
                config files from high-priority directory should be selected first.
                priority list (low to high):
                - default os-specific site config folder (/etc/xdg/utsc-tools/ on Linux, /Library/Application Support/utsc-tools/ on OSX, etc)
                - directory pointed to by {self.app_name}_SITE_CONFIG environment variable if set
                - cross-platform user config folder (~/.config/utsc-tools/ on all operating systems)
                - default os-specific user config folder (~/.config/at_utils on Linux, ~/Library/Application Support/utsc-tools/ on OSX, etc)
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

                - (PosixPath('/Library/Preferences/utsc-tools/shared.ini'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/shared.yaml'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/shared.json'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/shared.toml'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/example.ini'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/example.yaml'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/example.json'), File.unusable)
                - (PosixPath('/Library/Preferences/utsc-tools/example.toml'), File.unusable)
                - (PosixPath('/Users/alex/.config/utsc-tools/shared.ini'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/shared.yaml'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/shared.json'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/shared.toml'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/example.ini'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/example.yaml'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/example.json'), File.creatable)
                - (PosixPath('/Users/alex/.config/utsc-tools/example.toml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/shared.ini'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/shared.yaml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/shared.json'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/shared.toml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/example.ini'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/example.yaml'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/example.json'), File.creatable)
                - (PosixPath('/Users/alex/Library/Preferences/utsc-tools/example.toml'), File.creatable)

            """

            def file_names():
                for basename in ["shared", self.parent.app_name]:
                    for ext in ["ini", "yaml", "json", "toml"]:
                        yield f"{basename}.{ext}"

            for dir in self.dirs_generator():
                for name in file_names():
                    file = dir / name
                    yield file, File.state(file)

        @cached_property
        def files(self):
            res = list(self.files_generator())
            logger.bind(list=res).trace("Caching list of config files: ")
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
            File can be stored in a site-wide directory (ex. /etc/xdg/utsc-tools)
            or a user-local directory (ex. ~/.config/utsc-tools)
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
                raise UTSCCoreError(
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
                raise UTSCCoreError(
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

    class Logging:
        """
        Core class for CLI apps to simplify access to config files, cache directories, and logging configuration
        """

        parent: "Util"
        stderr_format: str
        syslog_format: str

        def __init__(self, parent: "Util") -> None:
            self.parent = parent

            self.stderr_format = f"<blue>{self.parent.app_name}</> | <level>{{level.name:8}}</>| <bold>{{message}}</>"
            self.syslog_format = f"{self.parent.app_name} | {{name}}:{{function}}:{{line}} - {{level.name: ^8}} | {{message}} | Data: {{extra}}"

        def add_stderr_sink(self, level="INFO", **kwargs):
            options = dict(
                backtrace=False,
                level=level,
                colorize=True,
                format=self.stderr_format,
            )
            options.update(kwargs)
            logger.add(sys.stderr, **options)

        def add_stderr_rich_sink(self, level="INFO", **kwargs):

            options = dict(
                backtrace=False,
                level=level,
                format=self.stderr_format,
            )
            options.update(kwargs)
            logger.add(self.parent.console.print, **options)

        def add_json_logfile_sink(self, filename=None, level="DEBUG", **kwargs):
            filename = filename or f"{self.parent.app_name}.log"
            options = dict(
                level=level,
                format="{message}",
                serialize=True,  # Convert {message} to a json string of the Message object
                rotation="5MB",  # How big should the log file get before it's rolled?
                retention=4,  # How many compressed copies to keep?
                compression="zip",
            )
            options.update(kwargs)
            logger.add(filename, **options)

        def add_syslog_sink(self, level="DEBUG", syslog_address=None, **kwargs):
            if platform.system() == "Windows":
                # syslog configs like level and facility don't apply in windows,
                # so we set up a basic event log handler instead
                handler = logging.handlers.NTEventLogHandler(
                    appname=self.parent.app_name
                )
            else:
                # should handle ~90% of unixes
                if syslog_address:
                    pass
                elif Path("/var/run/syslog").exists():
                    syslog_address = "/var/run/syslog"  # MacOS syslog
                elif Path("/dev/log").exists():
                    syslog_address = "/dev/log"  # Most Unixes?
                else:
                    syslog_address = ("localhost", 514)  # Syslog daemon
                handler = logging.handlers.SysLogHandler(address=syslog_address)
                handler.ident = "utsc-tools: "

            options = dict(level=level, format=self.syslog_format)
            options.update(kwargs)
            logger.add(handler, **options)

        def add_sentry_sink(self, level="ERROR", **kwargs):
            try:
                sentry_dsn = self.parent.config.get_key_or_fail("sentry_dsn")
            except KeyError:
                logger.debug(
                    "`sentry_dsn` option not found in any config file. Sentry logging disabled"
                )
                return None

            try:
                import sentry_sdk  # type: ignore
            except ImportError:
                logger.debug(
                    "the sentry_sdk package is not installed. Sentry logging disabled."
                )
                return None
            # the way we set up sentry logging assumes you have one sentry
            # project for all your apps, and want to group all your alerts
            # into issues by app name

            def before_send(event, hint):  # noqa
                # group all sentry events by app name
                if event.get("exception"):
                    exc_type = event["exception"]["values"][0]["type"]
                    event["exception"]["values"][0][
                        "type"
                    ] = f"{self.parent.app_name}: {exc_type}"
                if event.get("message"):
                    event["message"] = f'{self.parent.app_name}: {event["message"]}'
                return event

            sentry_sdk.init(
                sentry_dsn,
                with_locals=True,
                request_bodies="small",
                before_send=before_send,
            )
            user = {"username": getuser()}
            email = os.environ.get("MY_EMAIL")
            if email:
                user["email"] = email
            sentry_sdk.set_user(user)

            def sentry_sink(msg: "Message"):
                data = msg.record
                level = data["level"].name.lower()
                exception = data["exception"]
                message = data["message"]
                sentry_sdk.set_context("log_data", dict(data))
                if exception:
                    sentry_sdk.capture_exception()
                else:
                    sentry_sdk.capture_message(message, level)

            logger.add(sentry_sink, level=level, **kwargs)

        def enable(self):
            logger.remove()  # remove default handler, if it exists
            logger.enable("")  # enable all logs from all modules

            # setup python logger to forward all logs to loguru
            logging.basicConfig(handlers=[InterceptHandler()], level=0)

    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self.dirs: PlatformDirs = PlatformDirs("utsc-tools")
        self.console: Console = Console(stderr=True)
        self.logging: "Util.Logging" = self.Logging(self)
        self.config: "Util.Config" = self.Config(self)
        # there should be one config path which is common to all OS platforms,
        # so that users who sync configs betweeen multiple computers can sync
        # those configs to the same directory across machines and have it *just work*
        # By convention, this path is ~/.config/utsc-tools

    # region util
    def get_env_var(self, property):
        "fetches a namespaced environment variable"
        property = property.replace("-", "_").replace(
            ".", "_"
        )  # property names must have underscores, not dashes or dots
        env_var_name = f"{self.app_name}_{property}".upper()
        res = os.environ.get(env_var_name)
        msg = f"Environment variable '{env_var_name}' for property '{property}'"
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
            raise UTSCCoreError(
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


from .nested_data import *  # noqa

if __name__ == "__main__":
    from .other import *  # noqa

    u = Util(app_name="utsc-tools")
    v = Prompt(u).list_(var="test", description="hello description")
    print(v)
