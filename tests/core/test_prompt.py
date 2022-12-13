import os, sys
from enum import Enum, auto
from pathlib import Path
from typing import Literal
import select


from pydantic import BaseModel
from pydantic.types import SecretStr, DirectoryPath, FilePath
from uoft_core import StrEnum, Util
import pyte

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
    
def _wait_for_screen_update(child_pty_file_descriptor, vty_input_stream):
    """Wait for the child process to finish writing to "screen", pipe contents to the vty for analysis"""
    while True:
        try:
            [child_pty_file_descriptor], _, _ = select.select(
                [child_pty_file_descriptor], [], [], 1)
        except (KeyboardInterrupt, ValueError):
            # either test was interrupted or the
            # file descriptor of the child process
            # provides nothing to be read
            break
        else:
            try:
                # scrape screen of child process
                data = os.read(child_pty_file_descriptor, 1024)
                vty_input_stream.feed(data)
            except OSError:
                # reading empty
                break

def test_unmocked_prompt():
    # create pseudo-terminal
    pid, fd = os.forkpty()
    if pid == 0:
        # We are now in the child side of the fork
        # Here we will run the program we want to test
        p = Prompt(Util('prompt_test').history_cache)
        res = p.from_model(Ex)
        assert res
        sys.exit(0)
    else:
        # We are now in the parent side of the fork

        # create VTY
        screen = pyte.Screen(80, 24)
        stream = pyte.ByteStream(screen)
        # Here we will wait for the child to finish
        # writing to its stdout, and then we will
        # read the contents of the child's stdout
        # and feed it to the VTY for analysis
        _wait_for_screen_update(fd, stream)

        # First, we'll print out the contents of the VTY, so we can see what it looks like
        # in the event of a pytest failure
        for line in screen.display:
            print(line)

        # now, do some assertions and interact with the child process
        assert 'a_bool: ' in screen.display[0]
        
        
def test_mocked_prompt(monkeypatch: MonkeyPatch, tmp_path: Path):
    """Mock out prompt_toolkit's PromptSession as best we can, and test Prompt against our mock."""
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

    p = Prompt(Util('prompt_test').history_cache)
    res = p.from_model(Ex)
    assert res



def _debug():
    p = Prompt(Util('prompt_test').history_cache)
    print(p.from_model(Ex))
