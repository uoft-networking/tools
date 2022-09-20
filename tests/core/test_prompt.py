from enum import Enum, auto
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic.types import SecretStr, DirectoryPath, FilePath
from uoft_core import StrEnum, Util

from uoft_core.prompt import Prompt

class File(StrEnum):
    write = object()
    read = object()
    create = object()
    dont_use = object()

class MyEnum(Enum):
    choice1 = auto()
    choice2 = auto()
    choice3 = auto()
    

class Ex(BaseModel):
    a_bool: bool
    a_str: str
    an_int: int
    a_choice: Literal['one', 'two', 'three']
    an_enum: File 
    an_enum2: MyEnum
    a_path: Path 
    a_path2: DirectoryPath 
    a_path_3: FilePath
    a_str_list: list[str]
    an_int_list: list[int]
    a_dict: dict[str, str]

def test_():
    p = Prompt(Util('prompt_test'))
    for name, field in Ex.__fields__.items():
        p.from_model_field(name, field)