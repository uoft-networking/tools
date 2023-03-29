# pylint: disable=unused-argument
from pathlib import Path
from typing import TYPE_CHECKING

from at_utils import configure_logging

from .fixtures import module_a

from loguru import logger

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from _pytest.capture import CaptureFixture
    from at_utils.dev_utils import CapLoguru


def test_configure_logging(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
    capsys: "CaptureFixture",
    caploguru_manual: "CapLoguru",
):

    # logger should start disabled
    module_a.doathing()

    # logging by default is a no-op, unless and until logging is enabled.
    # no log file should exist yet
    assert len(list(tmp_path.iterdir())) == 0
    configure_logging(
        app_name="test",
        stderr_level="DEBUG",
        logfile_level=None,
        sentry_level=None,
        stderr_opts={"colorize": False},
        attach_stdlib_logger=True,
    )
    caploguru_manual.add_handler()
    # test basic configuration
    logger.info("When `logfile_level` is None, no file logging should occur")
    assert len(list(tmp_path.iterdir())) == 0

    # test sys.stderr sink
    assert (
        "When `logfile_level` is None, no file logging should occur"
        in capsys.readouterr().err
    )


def test_configure_logging_file_handling(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
    capsys: "CaptureFixture",
    caploguru_manual: "CapLoguru",
):
    # override the default log dir
    monkeypatch.setenv("DEFAULT_LOG_DIR", str(tmp_path))
    configure_logging(
        app_name="test",
        stderr_level="DEBUG",
        logfile_level="DEBUG",
        sentry_level=None,
        stderr_opts={"colorize": False},
    )
    caploguru_manual.add_handler()
    module_a.doathing()
    with logger.catch():
        print(1 / 0)
    logfile = tmp_path.joinpath("test.log")

    # test logfile output
    assert logfile.exists()
    logfile_output = logfile.read_text()
    assert (
        "This is a TRACE message" not in logfile_output
    ), "default file log level should not capture TRACE messages"
    assert (
        "This is a DEBUG message" in logfile_output
    ), "default file log level should capture DEBUG messages"
    assert (
        "An error has been caught in function" in logfile_output
    ), "log file should collect exception messages"


def test_attach_stdlib_logging(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
    capsys: "CaptureFixture",
    caploguru: "CapLoguru",
):
    configure_logging(
        app_name="test",
        stderr_level="DEBUG",
        logfile_level=None,
        sentry_level=None,
        stderr_opts={"colorize": False},
        attach_stdlib_logger=True,
    )
    caploguru.add_handler()
    module_a.doathing()
    assert True


def test_syslog_logging(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
    caploguru: "CapLoguru",
):
    configure_logging(
        app_name="test",
        stderr_level="DEBUG",
        logfile_level=None,
        sentry_level=None,
        syslog_level="DEBUG",
        stderr_opts={"colorize": False},
        attach_stdlib_logger=True,
    )
    caploguru.add_handler()
    module_a.doathing()
    assert True
