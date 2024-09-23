"""
Our own logging wrapper module.
Behaves exactly like the standard library logging module,
but with support for log contexts and custom log levels TRACE and SUCCESS."""

from typing import TYPE_CHECKING, Literal, Iterable, IO
import logging
from pathlib import Path
from contextvars import ContextVar

from .console import console

# exports
from logging import *  # noqa F401 # type: ignore

TRACE = 5
SUCCESS = 25
logging.addLevelName(TRACE, "TRACE")
logging.addLevelName(SUCCESS, "SUCCESS")

# set a new default logger class, which inherits from
# any default logger class which may have already been set
# by some other 3rd-party library
BaseLogger = logging.getLoggerClass()


class UofTCoreLogger(BaseLogger):
    def trace(self, msg, *args, **kwargs):
        self._log(TRACE, msg, args, **kwargs)

    def success(self, msg, *args, **kwargs):
        self._log(SUCCESS, msg, args, **kwargs)


logging.setLoggerClass(UofTCoreLogger)

_logging_contexts: ContextVar[set[str]] = ContextVar("logging_contexts", default=set())


class _ContextFilter(logging.Filter):
    def filter(self, record):
        contexts = _logging_contexts.get()
        if contexts:
            record.contexts = contexts
            msg = record.msg
            for context in contexts:
                msg = f"{context}: {msg}"
            record.msg = msg
        return True


def basicConfig(**kwargs):  # type: ignore
    """
    Do basic configuration for the logging system.

    This function does nothing if the root logger already has handlers
    configured, unless the keyword argument *force* is set to ``True``.
    It is a convenience method intended for use by simple scripts
    to do one-shot configuration of the logging package.

    The default behaviour is to create a StreamHandler which writes to
    sys.stderr, set a formatter using the BASIC_FORMAT format string, and
    add the handler to the root logger.

    A number of optional keyword arguments may be specified, which can alter
    the default behaviour.

    filename  Specifies that a FileHandler be created, using the specified
              filename, rather than a StreamHandler.
    filemode  Specifies the mode to open the file, if filename is specified
              (if filemode is unspecified, it defaults to 'a').
    format    Use the specified format string for the handler.
    datefmt   Use the specified date/time format.
    style     If a format string is specified, use this to specify the
              type of format string (possible values '%', '{', '$', for
              %-formatting, :meth:`str.format` and :class:`string.Template`
              - defaults to '%').
    level     Set the root logger level to the specified level.
    stream    Use the specified stream to initialize the StreamHandler. Note
              that this argument is incompatible with 'filename' - if both
              are present, 'stream' is ignored.
    handlers  If specified, this should be an iterable of already created
              handlers, which will be added to the root handler. Any handler
              in the list which does not have a formatter assigned will be
              assigned the formatter created in this function.
    force     If this keyword  is specified as true, any existing handlers
              attached to the root logger are removed and closed, before
              carrying out the configuration as specified by the other
              arguments.
    encoding  If specified together with a filename, this encoding is passed to
              the created FileHandler, causing it to be used when the file is
              opened.
    errors    If specified together with a filename, this value is passed to the
              created FileHandler, causing it to be used when the file is
              opened in text mode. If not specified, the default value is
              `backslashreplace`.
    log_errors_to_file
              If specified, log errors to a file. The default is False.
    error_log_filename
              If specified, the filename to log errors to. The default is 'errors.log'.
              Only used if log_errors_to_file is True.

    Note that you could specify a stream created using open(filename, mode)
    rather than passing the filename and mode in. However, it should be
    remembered that StreamHandler does not close its stream (since it may be
    using sys.stdout or sys.stderr), whereas FileHandler closes its stream
    when the handler is closed.

    .. versionchanged:: 3.2
       Added the ``style`` parameter.

    .. versionchanged:: 3.3
       Added the ``handlers`` parameter. A ``ValueError`` is now thrown for
       incompatible arguments (e.g. ``handlers`` specified together with
       ``filename``/``filemode``, or ``filename``/``filemode`` specified
       together with ``stream``, or ``handlers`` specified together with
       ``stream``.

    .. versionchanged:: 3.8
       Added the ``force`` parameter.

    .. versionchanged:: 3.9
       Added the ``encoding`` and ``errors`` parameters.
    """
    # our own implementation of basicConfig, except that instead of creating a StreamHandler
    # with sys.stderr, we create a rich handler with sys.stderr
    import os
    from rich.logging import RichHandler
    from rich.console import Console

    if "format" not in kwargs:
        # let the RichHandler manage time, level, and source. 
        # no need to bake them into the message string
        kwargs["format"] = "%(message)s"

    if "handlers" not in kwargs:
        handlers: list[logging.Handler] = []
        error_log_filename = kwargs.pop("error_log_filename", "errors.log")

        show_path = False
        level = kwargs.get("level", logging.INFO)
        if isinstance(level, str):
            level = logging._nameToLevel[level]
        if level <= logging.DEBUG:
            show_path = True

        handlers.append(RichHandler(console=console(), show_time=False, show_path=show_path))
        if kwargs.pop("log_errors_to_file", False):
            handlers.append(RichHandler(console=Console(file=open(error_log_filename, "a"))))

        # if `/var/log/uoft-tools` exists and is writable, log errors to `/var/log/uoft-tools/<error_log_filename>`
        # otherwise, log errors to `<error_log_filename>` in the current working directory
        log_dir = Path("/var/log/uoft-tools")
        if log_dir.exists() and log_dir.is_dir() and os.access(log_dir, os.W_OK):
            error_log_path = log_dir / error_log_filename
            handlers.append(RichHandler(console=Console(file=open(error_log_path, "a"))))

        kwargs["handlers"] = handlers

    # Logger-level filtering happens on a per-logger basis. If we register a filter with the root logger AFTER
    # a logger has already been instantiated (which is guaranteed to be true atleast for the `uoft_core` logger),
    # the filter will not be applied to the already instantiated logger.
    # The only way to ensure that the filter is applied to all loggers is to register the filter with the root logger
    # and *all* loggers that have been instantiated so far.
    _filter = _ContextFilter("ContextFilter")
    root_logger = logging.getLogger()
    root_logger.addFilter(_filter)
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):  # we don't want to add filters to loggin.PlaceHolder instances
            logger.addFilter(_filter)

    return logging.basicConfig(**kwargs)


class Context:
    def __init__(self, context_msg: str):
        self.context_msg = context_msg

    def __enter__(self):
        _logging_contexts.get().add(self.context_msg)

    def __exit__(self, *args):
        _logging_contexts.get().remove(self.context_msg)


if TYPE_CHECKING:
    from types import FrameType
    from os import PathLike

    def getLogger(name: str) -> "UofTCoreLogger": ...

    def currentframe() -> FrameType: ...

    def basicConfig(
        *,
        filename: str | PathLike[str] | None = ...,
        filemode: str = ...,
        format: str = ...,
        datefmt: str | None = ...,
        style: Literal["%", "{", "$"] = ...,
        level: int | str | None = ...,
        stream: IO[str] | None = ...,
        handlers: Iterable[logging.Handler] | None = ...,
        force: bool | None = ...,
        encoding: str | None = ...,
        errors: str | None = ...,
        log_errors_to_file: bool = ...,
        error_log_filename: str = ...,
    ) -> None: ...
