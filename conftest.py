"""
This module serves as our own internal pytest plugin for use across all uoft-tools projects

It is not intended to be used by external projects, and is not installed as part of the package

It is loaded automatically by pytest because it is referenced in the pytest_plugins list in
the conftest.py file at the root of this repository
"""
from typing import TYPE_CHECKING
import logging
from pathlib import Path
import os
from uoft_core.tests import MockFolders
from uoft_core import logging

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from _pytest.fixtures import FixtureRequest

if os.getenv("VSCODE_DEBUGGER"):
    # set up hooks for VSCode debugger to break on exceptions
    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call):
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo):
        raise excinfo.value
    
    # enable logging to stderr when running tests in the debugger
    import logging
    configured = False
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream.name == "<stderr>":
                configured = True
                break
    if not configured:
        logging.basicConfig(level=logging.DEBUG)

@pytest.fixture()
def mock_util(tmp_path: Path, mocker: "MockerFixture", request: "FixtureRequest"):
    marker = request.node.get_closest_marker("app_name")
    app_name = marker.args[0] if marker else "example_app"

    import uoft_core

    # To test the config file testing logic of the Util class, we need to mock out all the system calls
    # it makes to return repeatable, predictable paths we can control, regardless of which platform
    # the test is running on, or what config files / folcers may already exists
    # in the *real* locations returned by these calls
    folders = MockFolders(tmp_path, app_name)  # create the folders to use as mocks

    # mock out the real folders
    mocker.patch.object(
        uoft_core.PlatformDirs, "site_config_path", folders.site_config.dir
    )
    mocker.patch.object(
        uoft_core.PlatformDirs, "user_config_path", folders.user_config.dir
    )
    mocker.patch.object(
        uoft_core.PlatformDirs, "site_data_path", folders.site_cache.parent
    )
    mocker.patch.object(
        uoft_core.PlatformDirs, "user_cache_path", folders.user_cache.parent
    )

    util = uoft_core.Util(app_name)  # create the Util instance to be tested

    mocker.patch.object(util.config, "common_user_config_dir", folders.user_config.dir)

    util.mock_folders = folders  # type: ignore

    yield util

    # clean up the file permissions so that the tmp_path directory can be cleaned up
    for f in folders.root.rglob("*"):
        f.chmod(0o777)

    # clean up the Util instance
    del util.mock_folders  # type: ignore
    util._clear_caches()


############
# Some of the following hooks configure the integration and end_to_end markers and their command line options
# They are based on the pytest-integration plugin, but modified to work with our own markers
# https://github.com/jbwdevries/pytest-integration/blob/master/pytest_integration/pytest_plugin.py
############
# region pytest-hooks


def pytest_addoption(parser: pytest.Parser, pluginmanager):
    """
    Adds configuration options to enable integration and end-to-end tests
    """
    del pluginmanager  # not needed in this context

    group = parser.getgroup("uoft-tools", "uoft-tools options")

    group.addoption(
        "--integration",
        action="store_const",
        default=False,
        const=True,
        dest="run_integration",
        help="Run integration tests (disabled by default)",
    )
    group.addoption(
        "--no-integration",
        action="store_const",
        const=False,
        dest="run_integration",
        help="Do not run integration tests (default)",
    )
    group.addoption(
        "--end-to-end",
        action="store_const",
        default=False,
        const=True,
        dest="run_end_to_end",
        help="Run end-to-end tests (disabled by default)",
    )
    group.addoption(
        "--no-end-to-end",
        action="store_const",
        const=False,
        dest="run_end_to_end",
        help="Do not run end-to-end tests (default)",
    )


def pytest_configure(config: pytest.Config):
    """
    Adds markers for integration and end-to-end tests
    """
    config.addinivalue_line(
        "markers", "integration: mark test to run after unit tests " "are complete"
    )

    config.addinivalue_line(
        "markers",
        "end_to_end: mark test to run after unit tests "
        "and (quick) integration tests are complete",
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items: list[pytest.Item]):
    """
    Sorts the items; unit test first, then integration tests, then
    end-to-end tests.
    """
    del session, config
    def _get_items_key(item: pytest.Item):
        if item.get_closest_marker("end_to_end"):
            return 2

        if item.get_closest_marker("integration"):
            return 1

        return 0

    items.sort(key=_get_items_key)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item):
    """
    Checks whether tests should be skipped based on markers and command-line flags,
    and environment variables
    """
    if os.getenv("RUN_ALL_TESTS") or os.getenv("VSCODE_DEBUGGER"):
        return

    if item.get_closest_marker("integration"):
        if item.config.getoption("run_integration") in (None, True):
            return
        pytest.skip("Integration tests skipped")

    if item.get_closest_marker("end_to_end"):
        if item.config.getoption("run_end_to_end") in (None, True):
            return
        pytest.skip("End-to-end tests skipped")


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Turns off running integration tests or end-to-end tests
    if one of the previous stages failed.
    """
    if item.get_closest_marker("xfail"):
        return

    if not call.excinfo or call.excinfo.value.__class__.__name__ == "Skipped":
        return

    if item.get_closest_marker("end_to_end"):
        return

    item.config.option.run_end_to_end = False

    if item.get_closest_marker("integration"):
        return

    item.config.option.run_integration = False


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_itemcollected(item: pytest.Item):
    "Rename all pytest Package items to match their folder structure"
    parent = item.parent # type: ignore
    while not isinstance(parent, pytest.Package):
        parent = parent.parent # type: ignore

    parent: pytest.Package
    parent.name = str(item.path.parent.relative_to(item.session.config.rootpath))
    yield
# endregion pytest-markers
