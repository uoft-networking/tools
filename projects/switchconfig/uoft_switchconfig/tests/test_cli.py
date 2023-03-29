# pylint: disable=unused-argument
from typing import TYPE_CHECKING
from pathlib import Path
from uoft_switchconfig import Settings
from uoft_switchconfig.cli import template_name_completion, console_name_completion
from uoft_core import txt

if TYPE_CHECKING:
    from pytest_mock import MockFixture
    from _pytest.logging import LogCaptureFixture


def test_template_name_completion():
    class MockContext:
        params = {"cache_dir": Path(__file__).parent / "fixtures/templates"}

    res = template_name_completion(MockContext(), "")  # type: ignore
    assert set(res) == set(
        [
            "comment-block-schema-test.j2",
            "data-model-test.j2",
            "subdirectory/template.j2",
            "subdirectory/other_template.j2",
        ]
    )

    res = template_name_completion(MockContext(), "subdir")  # type: ignore
    assert set(res) == set(
        [
            "subdirectory/template.j2",
            "subdirectory/other_template.j2",
        ]
    )

    res = template_name_completion(MockContext(), "subdirectory/tem")  # type: ignore
    assert set(res) == set(
        [
            "subdirectory/template.j2",
        ]
    )


def test_console_name_completion(mocker: "MockFixture"):
    mock_settings = Settings(
        generate={"templates_dir": Path(__file__).parent / "templates"}, # type: ignore
        deploy=dict( # type: ignore
            ssh_pass_cmd="echo ssh_pass",
            terminal_pass_cmd="echo terminal_pass",
            enable_pass_cmd="echo enable_pass",
            targets=dict(
                airconsole1="airconsole:4001",
                airconsole2="airconsole:4002",
                airconsole3="airconsole:4003",
                airconsole4="airconsole:4004",
                airconsole5="airconsole:4005",
                airconsole6="airconsole:4006",
                airconsole7="airconsole:4007",
                airconsole8="airconsole:4008",
                newconsole="console:22",
            )
        ),
    )
    mocker.patch.object(Settings, '_instance', mock_settings)
    res = console_name_completion("")
    assert set(res) == set(
        [
            "airconsole1",
            "airconsole2",
            "airconsole3",
            "airconsole4",
            "airconsole5",
            "airconsole6",
            "airconsole7",
            "airconsole8",
            "newconsole",
        ]
    )

    res = console_name_completion("newco")
    assert res == ["newconsole"]
