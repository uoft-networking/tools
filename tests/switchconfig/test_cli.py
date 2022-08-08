# pylint: disable=unused-argument
from typing import TYPE_CHECKING
from pathlib import Path
from uoft_switchconfig.__main__ import template_name_completion, console_name_completion
from uoft_core import txt

if TYPE_CHECKING:
    from . import MockedConfig
    from _pytest.logging import LogCaptureFixture


def test_template_name_completion(mock_config):
    class MockContext:
        params = {"cache_dir": Path(__file__).parent / "templates"}

    res = template_name_completion(MockContext(), "")
    assert set(res) == set(
        [
            "comment-block-schema-test.j2",
            "data-model-test.j2",
            "subdirectory/template.j2",
            "subdirectory/other_template.j2",
        ]
    )

    res = template_name_completion(MockContext(), "subdir")
    assert set(res) == set(
        [
            "subdirectory/template.j2",
            "subdirectory/other_template.j2",
        ]
    )

    res = template_name_completion(MockContext(), "subdirectory/tem")
    assert set(res) == set(
        [
            "subdirectory/template.j2",
        ]
    )


def test_console_name_completion(mock_config: "MockedConfig"):
    mock_config.util.mock_folders.site_config.toml_file.write_text(
        txt(
            """
            [deploy]
            ssh_pass_cmd = ""
            terminal_pass_cmd = ""
            enable_pass_cmd = ""

            [deploy.targets]
            airconsole1 = "airconsole:4001"
            airconsole2 = "airconsole:4002"
            airconsole3 = "airconsole:4003"
            airconsole4 = "airconsole:4004"
            airconsole5 = "airconsole:4005"
            airconsole6 = "airconsole:4006"
            airconsole7 = "airconsole:4007"
            airconsole8 = "airconsole:4008"
            newconsole = "console:22"
            """
        )
    )

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
