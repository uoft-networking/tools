from importlib import metadata

__version__ = metadata.version(__name__)


from nautobot.extras.plugins import PluginConfig


class UofTPluginConfig(PluginConfig):
    name = "uoft_nautobot"
    verbose_name = "UofT Nautobot Plugin"
    author = "Alex Tremblay"
    author_email = "alex.tremblay@utoronto.ca"
    version = __version__
    description = "A Plugin containing all the extensions and customizations to Nautobot that the UofT networking teams need"
    base_url = "utsc"  # Needs to remain utsc for backwards compatibility
    min_version = "0.9"
    max_version = "9.0"
    middleware = []
    installed_apps = []
    default_settings = {}


def print_config_path():
    from pathlib import Path

    print(Path(__file__).parent.joinpath("nautobot_config.py"))


config = UofTPluginConfig  # noqa
