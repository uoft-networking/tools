import logging
from pathlib import Path
from uoft_core import Util


class PropogateHandler(logging.Handler):
    def emit(self, record):
        logging.getLogger(record.name).handle(record)


class MockFolders:
    class ConfDir:
        def __init__(self, path: Path, app_name: str) -> None:
            self.dir = path
            self.ini_file = path.joinpath(f"{app_name}.ini")
            self.json_file = path.joinpath(f"{app_name}.json")
            self.yaml_file = path.joinpath(f"{app_name}.yaml")
            self.toml_file = path.joinpath(f"{app_name}.toml")

    def __init__(self, tmp_path: Path, app_name: str) -> None:
        self.root = tmp_path
        self.site_config = MockFolders.ConfDir(
            tmp_path / "etc/xdg/uoft-tools", app_name
        )
        # This would be:
        # - /Library/Application Support/uoft-tools on MacOS,
        # - /etc/xdg/uoft-tools on Linux,
        # - C:\ProgramData\uoft-tools on Win 7+

        # an alternative site config path, used to test the *_SITE_CONFIG env var logic
        self.site_config_env = MockFolders.ConfDir(tmp_path / "etc/alternate", app_name)

        self.user_config = MockFolders.ConfDir(
            tmp_path / "home/user/.config/uoft-tools", app_name
        )
        # This would be:
        # - ~/Library/Application Support/uoft-tools on MacOS,
        # - ~/.config/uoft-tools on Linux,
        # - C:\Users\<username>\AppData\Local\uoft-tools on Win 7+

        # an alternative user config path, used to test the *_USER_CONFIG env var logic
        self.user_config_env = MockFolders.ConfDir(
            tmp_path / "home/alternate", app_name
        )

        self.site_cache = tmp_path / f"usr/local/share/uoft-tools/{app_name}"
        self.user_cache = tmp_path / f"home/user/.local/share/uoft-tools/{app_name}"
        self.site_cache_env = tmp_path / "usr/local/share/uoft-tools/alternate"
        self.user_cache_env = tmp_path / "home/user/.local/share/uoft-tools/alternate"

        # create the folders
        self.site_config.dir.mkdir(parents=True)
        self.site_config_env.dir.mkdir(parents=True)
        self.user_config.dir.mkdir(parents=True)
        self.user_config_env.dir.mkdir(parents=True)
        self.site_cache.mkdir(parents=True)
        self.user_cache.mkdir(parents=True)


class MockedUtil(Util):
    mock_folders: MockFolders
