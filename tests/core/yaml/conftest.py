import pytest
import monkeytype

@pytest.fixture(scope='session', autouse=True)
def mt():
    with monkeytype.trace():
        yield