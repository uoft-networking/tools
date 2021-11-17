from functools import cached_property
import sys

from utsc.core import Util, shell

from pydantic import BaseModel

__version__ = '0.1.2'

APP_NAME = 'scripts'

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
