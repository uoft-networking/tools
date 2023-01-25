from uoft_core import BaseSettings, SecretStr
import os
from _pytest.monkeypatch import MonkeyPatch

class Settings(BaseSettings):
    a_value: str = "a_value"
    secret: SecretStr

    class Config(BaseSettings.Config):
        app_name = "test"

def test_settings_env(monkeypatch: MonkeyPatch) -> None:
    for k in os.environ:
        monkeypatch.delenv(k)
    monkeypatch.setattr("os.isatty", lambda fd: False)
    monkeypatch.setenv("UOFT_TEST_SECRET", "my_secret")
    t = Settings.from_cache()
    assert t.secret.get_secret_value() == "my_secret"
