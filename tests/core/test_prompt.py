from enum import Enum, auto
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic.types import SecretStr, DirectoryPath, FilePath
from uoft_core import StrEnum, Util

from uoft_core.prompt import Prompt

from _pytest.monkeypatch import MonkeyPatch

class File(StrEnum):
    write = object()
    read = object()
    create = object()
    dont_use = object()

class MyEnum(Enum):
    choice1 = auto()
    choice2 = auto()
    choice3 = auto()
    
class Sub(BaseModel):
    sub_a: str
    sub_b: str

class Ex(BaseModel):
    a_bool: bool
    a_str: str
    a_password: SecretStr
    an_int: int
    a_choice: Literal['one', 'two', 'three']
    an_enum: File
    another_enum: MyEnum
    a_path: Path 
    a_dirpath: DirectoryPath 
    a_filepath: FilePath
    a_list_of_str: list[str]
    a_dict_of_str: dict[str, str]
    a_model: Sub


def test_prompt_with_valid_inputs(monkeypatch: MonkeyPatch, tmp_path: Path):
    class mockdoc:
        def __init__(self, v) -> None:
            self.text = v

    class mocksession:
        def __init__(self, **kwargs) -> None:
            pass

        def prompt(self, message, **kwargs):
            v = message.value
            if 'a_bool' in v:
                val = 'true'
            elif 'a_str' in v:
                val = 'hello'
            elif 'a_password' in v:
                val = 'secretsecret'
            elif 'an_int' in v:
                val = '1'
            elif 'a_choice' in v:
                val = 'one'
            elif 'an_enum' in v:
                val = 'read'
            elif 'another_enum' in v:
                val = 'choice1'
            elif 'a_path' in v:
                val = str(tmp_path / 'some_file')
            elif 'a_dirpath' in v:
                val = str(tmp_path)
            elif 'a_filepath' in v:
                p = tmp_path / 'a_real_file'
                p.touch()
                val = str(p)
            elif 'a_list_of_str' in v:
                val = 'one\ntwo\nthree'
            elif 'an_int_list' in v:
                val = '1\n2\n3'
            elif 'a_dict_of_str' in v:
                val = 'one: a\ntwo: b\nthree: c'
            elif 'a_model.sub' in v:
                val = 'some string'
            else:
                raise Exception('Uhoh, a test case for this type hasn\'t been implemented yet :(')
            val = mockdoc(val)
            if kwargs.get('validator'):
                kwargs['validator'].validate(val)
            return val.text

    monkeypatch.setattr('uoft_core.prompt.PromptSession', mocksession)

    p = Prompt(Util('prompt_test'))
    res = p.from_model(Ex)
    assert res

if __name__ == "__main__":
    p = Prompt(Util('prompt_test'))
    print(p.from_model(Ex))