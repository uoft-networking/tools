from importlib import metadata

__version__ = metadata.version(__name__)


from nautobot.extras.plugins import PluginConfig


class UTSCPluginConfig(PluginConfig):
    name = "nautobot_utsc"
    verbose_name = "UTSC Nautobot Plugin"
    author = "Alex Tremblay"
    author_email = "alex.tremblay@utoronto.ca"
    version = __version__
    description = "A Plugin containing all the extensions and customizations to Nautobot that the UTSC networking team needs"
    base_url = "utsc"
    min_version = "0.9"
    max_version = "9.0"
    middleware = []
    installed_apps = []
    default_settings = {}

    # URL reverse lookup names
    # home_view_name = "plugins:utsc:home"
    # config_view_name = "plugins:utsc:config"


config = UTSCPluginConfig # noqa
