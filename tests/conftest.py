from typing import TYPE_CHECKING
import logging
from pathlib import Path

from . import MockFolders

import pytest
from _pytest.logging import caplog as _caplog  # noqa
from loguru import logger

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from _pytest.logging import LogCaptureFixture
    from _pytest.fixtures import FixtureRequest

@pytest.fixture
def caplog(caplog: "LogCaptureFixture"):
    """
    override and wrap the caplog fixture with one of our own
    """
    logger.remove()  # remove default handler, if it exists
    logger.enable("")  # enable all logs from all modules
    logging.addLevelName(5, "TRACE")  # tell python logging how to interpret TRACE logs

    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    # shunt logs into the standard python logging machinery
    logger.add(PropogateHandler(), format="{message} {extra}", level="TRACE")
    caplog.set_level(0)  # Tell logging to handle all log levels
    yield caplog

@pytest.fixture()
def mock_folders(tmp_path: Path, mocker: "MockerFixture", request: "FixtureRequest"):
    marker = request.node.get_closest_marker("app_name")
    app_name = marker.args[0] if marker else "example_app"
    
    import utsc.core  # noqa

    # To test the config file testing logic of the Util class, we need to mock out all the system calls
    # it makes to return repeatable, predictable paths we can control, regardless of which platform
    # the test is running on, or what config files / folcers may already exists
    # in the *real* locations returned by these calls
    folders = MockFolders(tmp_path, app_name)  # create the folders to use as mocks

    # mock out the real folders
    mocker.patch.object(
        utsc.core.PlatformDirs, "site_config_path", folders.site_config.dir
    )
    mocker.patch.object(
        utsc.core.PlatformDirs, "user_config_path", folders.user_config.dir
    )
    mocker.patch.object(
        utsc.core.PlatformDirs, "site_data_path", folders.site_cache.parent
    )
    mocker.patch.object(
        utsc.core.PlatformDirs, "user_cache_path", folders.user_cache.parent
    )

    util = utsc.core.Util(app_name)  # create the Util instance to be tested

    mocker.patch.object(util.config, "common_user_config_dir", folders.user_config.dir)
    yield util, folders

    # clean up the file permissions so that the tmp_path directory can be cleaned up
    for f in folders.root.rglob("*"):
        f.chmod(0o777)

    # clean up the Util instance
    util._clear_caches()  # noqa