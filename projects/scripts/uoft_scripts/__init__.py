from functools import cached_property
import sys
from importlib.metadata import version

from uoft_core import Util, shell

from loguru import logger
from pydantic import BaseModel

__version__ = version(__package__)

logger.disable(__name__)

APP_NAME = "scripts"


class Bluecat(BaseModel):
    url: str
    username: str
    password_cmd: str

    @property
    def password(self):
        return shell(self.password_cmd)


class ConfigModel(BaseModel):
    bluecat: Bluecat


class Config:
    def __init__(self) -> None:
        self.util = Util(APP_NAME)

    @cached_property
    def data(self):

        conf = self.util.config.get_data_from_model(ConfigModel)
        return ConfigModel(**conf)


config = Config()
