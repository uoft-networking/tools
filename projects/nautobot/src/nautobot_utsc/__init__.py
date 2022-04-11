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


def debug(nbshell_namespace):
    """
    Entrypoint for the vscode debugger. 
    To use, run `nbshell --command "from nautobot_utsc import debug; debug(globals())"`
    in your debugger
    """
    from .diffsync.bluecat.adapters import Bluecat, Nautobot
    b = Bluecat(job=None)
    n = Nautobot(job=None)
    print(b.diff_to(n))


config = UTSCPluginConfig # noqa
