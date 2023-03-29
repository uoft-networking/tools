from ..librenms import Settings
import pytest

@pytest.mark.skip(reason="WIP")
class LibreNMS:
    def happy_path(self, mocker):
        s = Settings.from_cache()
