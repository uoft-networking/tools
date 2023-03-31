from .. import Settings
import pytest

@pytest.mark.end_to_end
class LibreNMS:
    def happy_path(self, ):
        s = Settings.from_cache()
        api = s.api_connection()
        d = api.devices.list_devices()
