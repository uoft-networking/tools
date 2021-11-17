from functools import cached_property
from pathlib import Path
import sys
from typing import TYPE_CHECKING
from importlib.metadata import version

from utsc.core import Util

from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from tests.switchconfig import templates
    TemplatesModule = templates

__version__ = version(__package__)

logger.disable(__name__)

APP_NAME = 'switchconfig'

def _default_templates_dir():
    return config.util.cache_dir / 'templates'

class ConfigModel(BaseModel):
    ssh_pass_cmd: str
    terminal_pass_cmd: str
    enable_pass_cmd: str
    deploy_targets: dict[str, str]
    templates_dir: Path = Field(default_factory=_default_templates_dir)
    debug: bool = False

class Config:
    def __init__(self) -> None:
        self.util = Util(APP_NAME)

    @cached_property
    def data(self):

        conf = self.util.config.get_data_from_model(ConfigModel)
        return ConfigModel(**conf)

    @property
    def templates(self) -> 'TemplatesModule':
        orig_sys_path = sys.path.copy()
        if (local := Path("templates")).exists():
            logger.debug(f"Loading templates from current directory: {Path().resolve()}")
            path = local
        elif self.data.templates_dir.exists():
            logger.debug(f"Loading templates from site template directory: {self.data.templates_dir}")
            path = self.data.templates_dir
        else:
            raise FileNotFoundError('No templates directory found. ')
        
        sys.path.insert(0, str(path))
        try:
            import templates # type: ignore # noqa
        except ImportError as e:
            # Do the import by hand
            module_name = 'templates'
            from importlib.util import spec_from_file_location, module_from_spec # noqa
            if module_name not in sys.modules:
                spec = spec_from_file_location(module_name, str(path / 'templates.py'))
                if spec is None:
                    raise FileNotFoundError('No templates directory found. ') from e
                module = module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(module)
                sys.modules[module_name] = module
            templates = sys.modules[module_name]
        sys.path = orig_sys_path
        return templates # type: ignore

        


config = Config()
