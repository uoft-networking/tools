from ..librenms import Settings
import pytest

@pytest.mark.end_to_end
class LibreNMS:
    def happy_path(self, mocker):
        s = Settings.from_cache()
        print(s)
