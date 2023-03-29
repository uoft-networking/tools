from at_utils.dev_utils import (
    caploguru_base,
    caploguru_manual,
    CapLoguru,
    mock_at_utils_paths,
    SIUtilsPaths,
)  # noqa

import pytest


@pytest.fixture
def mock_paths(mock_at_utils_paths) -> SIUtilsPaths:  # noqa
    return mock_at_utils_paths("test")


@pytest.fixture
def caploguru(caploguru_base) -> CapLoguru:  # noqa
    return caploguru_base("test")
