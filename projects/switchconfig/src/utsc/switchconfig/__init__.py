from functools import cached_property
from typing import Optional
from importlib.metadata import version

from pydantic.types import DirectoryPath

from utsc.core import Util

from loguru import logger
from pydantic import BaseModel, Field

__version__ = version(__package__)

logger.disable(__name__)

APP_NAME = "switchconfig"


def _default_templates_dir():
    return config.util.cache_dir / "templates"


class ConfigGenerateModel(BaseModel):
    templates_dir: DirectoryPath = Field(default_factory=_default_templates_dir)


class ConfigDeployModel(BaseModel):
    ssh_pass_cmd: str
    terminal_pass_cmd: str
    enable_pass_cmd: str
    targets: dict[str, str]


class ConfigModel(BaseModel):
    generate: Optional[ConfigGenerateModel]
    deploy: Optional[ConfigDeployModel]
    debug: bool = False


class Config:
    def __init__(self) -> None:
        self.util = Util(APP_NAME)

    @cached_property
    def data(self):

        conf = self.util.config.get_data_from_model(ConfigModel)
        return ConfigModel(**conf)


config = Config()
