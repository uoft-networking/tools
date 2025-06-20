from functools import cached_property
from typing import Optional
from importlib.metadata import version
from pathlib import Path

from uoft_core import Util, UofTCoreError, chomptxt, BaseSettings, logging

from pydantic.v1 import BaseModel, Field

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore

logger = logging.getLogger(__name__)

APP_NAME = "switchconfig"


def _default_templates_dir():
    return config.util.cache_dir / "templates"


class Generate(BaseModel):
    templates_dir: Path = Field(
        default_factory=_default_templates_dir,
        description="override the default template cache directory",
    )


class Deploy(BaseModel):
    ssh_pass_cmd: str = Field(
        description="shell command to aquire the console server ssh password"
    )
    terminal_pass_cmd: str = Field(
        description="shell command to aquire the switch's terminal access password"
    )
    enable_pass_cmd: str = Field(
        description="shell command to aquire the switch's enable password"
    )
    targets: dict[str, str] = Field(
        description=chomptxt(
            """
            a table / dictionary of console servers, mapping console server 
            names to console server hostname/fqdn+port combinations
            """
        )
    )


class ConfigModel(BaseModel):
    generate: Optional[Generate] = Field(
        None,
        description="whether to include any overriding configuration related to the generate command",
    )
    deploy: Optional[Deploy] = Field(
        None,
        description="whether to include any overriding configuration related to the deploy command",
    )
    debug: bool = Field(False, description="whether to permanently enable debug mode")


class Config:
    def __init__(self) -> None:
        self.util = Util(APP_NAME)

    @cached_property
    def data(self):
        try:
            conf = self.util.config.get_data_from_model(ConfigModel)
            return ConfigModel(**conf)
        except UofTCoreError as e:
            logger.exception("Failed to load configuration", exc_info=e)
            return None


config = Config()


class Settings(BaseSettings):
    generate: Generate = Field(
        None,
        description="whether to include any overriding configuration related to the generate command",
    )
    deploy: Deploy = Field(
        None,
        description="whether to include any overriding configuration related to the deploy command",
    )
    debug: bool = Field(False, description="whether to permanently enable debug mode")

    class Config(BaseSettings.Config):
        app_name = 'switchconfig'

settings = Settings.from_cache
