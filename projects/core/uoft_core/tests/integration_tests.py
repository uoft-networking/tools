import os
import pytest
import enum
from pathlib import Path
from typing import Literal, TYPE_CHECKING
import select
from pydantic.v1 import BaseModel
import uoft_core
import uoft_core.prompt
from uoft_core.types import SecretStr, DirectoryPath, FilePath

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch # pyright: ignore[reportPrivateImportUsage]

class _Settings(uoft_core.BaseSettings):
    a_value: str = "a_value"
    secret: SecretStr

    class Config(uoft_core.BaseSettings.Config):
        app_name = "test"


@pytest.mark.integration
class SettingsTests:
    def test_from_env_vars(self, monkeypatch: 'MonkeyPatch') -> None:
        for k in os.environ:
            monkeypatch.delenv(k)
        monkeypatch.setattr("os.isatty", lambda fd: False)
        monkeypatch.setenv("UOFT_TEST_SECRET", "my_secret")
        t = _Settings.from_cache()
        assert t.secret.get_secret_value() == "my_secret"


class _File(uoft_core.StrEnum):
    write = object()
    read = object()
    create = object()
    dont_use = object()


class _StdLibEnum(enum.Enum):
    choice1 = enum.auto()
    choice2 = enum.auto()
    choice3 = enum.auto()


class _SubModel(BaseModel):
    sub_a: str
    sub_b: str


class _Example(BaseModel):
    a_bool: bool
    a_str: str
    a_password: SecretStr
    an_int: int
    a_choice: Literal["one", "two", "three"]
    an_enum: _File
    another_enum: _StdLibEnum
    a_path: Path
    a_dirpath: DirectoryPath
    a_filepath: FilePath
    a_list_of_str: list[str]
    a_dict_of_str: dict[str, str]
    a_model: _SubModel


@pytest.mark.integration
class PromptTests:
    def _wait_for_screen_update(self, child_pty_file_descriptor, vty_input_stream):
        """Wait for the child process to finish writing to "screen", pipe contents to the vty for analysis"""
        while True:
            try:
                [child_pty_file_descriptor], _, _ = select.select([child_pty_file_descriptor], [], [], 1)
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

    def test_mocked_prompt(self, monkeypatch: 'MonkeyPatch', tmp_path: Path):
        """Mock out prompt_toolkit's PromptSession as best we can, and test Prompt against our mock."""

        class mockdoc:
            def __init__(self, v) -> None:
                self.text = v

        class mocksession:
            def __init__(self, **kwargs) -> None:
                pass

            def prompt(self, message, **kwargs):
                v = message.value
                if "a_bool" in v:
                    val = "true"
                elif "a_str" in v:
                    val = "hello"
                elif "a_password" in v:
                    val = "secretsecret"
                elif "an_int" in v:
                    val = "1"
                elif "a_choice" in v:
                    val = "one"
                elif "an_enum" in v:
                    val = "read"
                elif "another_enum" in v:
                    val = "choice1"
                elif "a_path" in v:
                    val = str(tmp_path / "some_file")
                elif "a_dirpath" in v:
                    val = str(tmp_path)
                elif "a_filepath" in v:
                    p = tmp_path / "a_real_file"
                    p.touch()
                    val = str(p)
                elif "a_list_of_str" in v:
                    val = "one\ntwo\nthree"
                elif "an_int_list" in v:
                    val = "1\n2\n3"
                elif "a_dict_of_str" in v:
                    val = "one: a\ntwo: b\nthree: c"
                elif "a_model.sub" in v:
                    val = "some string"
                else:
                    raise Exception("Uhoh, a test case for this type hasn't been implemented yet :(")
                val = mockdoc(val)
                if kwargs.get("validator"):
                    kwargs["validator"].validate(val)
                return val.text

        monkeypatch.setattr("uoft_core.prompt.PromptSession", mocksession)

        p = uoft_core.prompt.Prompt(uoft_core.Util("prompt_test").history_cache)
        res = p.from_model(_Example)
        assert res
