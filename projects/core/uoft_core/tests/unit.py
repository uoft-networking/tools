# pylint: disable=unused-argument
import uoft_core

import pytest

from pathlib import Path
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import MockedUtil
    from pytest_mock import MockerFixture
    from _pytest.logging import LogCaptureFixture


def test_version():
    assert isinstance(uoft_core.__version__, str)


def test_txt():
    res = uoft_core.txt(
        """
        one
        two
        three
        """
    )
    assert res == "one\ntwo\nthree\n"


def test_chomptxt():
    res = uoft_core.chomptxt(
        """
        one
        two
        three
        """
    )
    assert res == "one two three"

    res = uoft_core.chomptxt(
        """
        one

        two
        three
        """
    )
    assert res == "one\ntwo three"


def test_lst():
    res = uoft_core.lst(
        """
        one # superfluous comment
        two

        # empty space and line comment
        three
        """
    )
    assert res == ["one", "two", "three"]


def test_file(tmp_path: Path):
    """
    A file should be considered writable if it exists and can be written to.
    A file should be readable if it exists, can be read from, but cannot be written to.
    A file should be creatable if it doesn't exist but it's parent directory is writable
    A file should be unusable if it either exists but cannot be read,
        or if it doesn't exist and its parent dir is not writable
    """
    # tmp_path is writable, and the "creatable" file doesn't exist,
    # so it should come up as creatable
    creatable = tmp_path / "creatable"

    readable = tmp_path / "readable"
    readable.touch(mode=0o444)

    writable = tmp_path / "writable"
    writable.touch(mode=0o666)

    unusable = tmp_path / "readonly-dir/unusable"
    unusable.parent.mkdir(mode=0o444)

    assert uoft_core.File.is_creatable(creatable)
    assert uoft_core.File.state(creatable) == uoft_core.File.creatable

    assert uoft_core.File.is_readable(readable)
    assert uoft_core.File.state(readable) == uoft_core.File.readable

    assert uoft_core.File.is_writable(writable)
    assert uoft_core.File.state(writable) == uoft_core.File.writable

    assert uoft_core.File.state(unusable) == uoft_core.File.unusable

    for f in tmp_path.rglob("*"):
        f.chmod(0o777)  # restore perms so the tmp_path can be cleaned up


def test_timeit():
    # the clock starts as soon as the class is initialized
    timer = uoft_core.Timeit()
    time.sleep(0.15)
    timer.interval()  # record an interval

    # Timeit class uses time.perf_counter, which doesn't play nice with time.sleep
    # inside of pytest. we have to make our assert tolerances extremely sloppy
    # to account for that.
    # outside of pytest, this issue is difficult to replicate
    assert 0.149 < timer.float < 0.156
    assert timer.str.startswith("0.149") or timer.str.startswith("0.15")

    time.sleep(0.05)
    timer.interval()

    # only the time elapsed since the start
    # of the last interval is recorded
    assert 0.049 < timer.float < 0.056
    assert timer.str.startswith("0.049") or timer.str.startswith("0.05")

    # timer.interval() is the same as timer.stop() except it starts a new
    # clock immediately after recording runtime for the previous clock
    timer.stop()


class Utils:
    def test_config_files(self, mock_util: "MockedUtil", caplog: "LogCaptureFixture"):
        """
        the `config_files` property of the `Util` class should return a list of (path, state) pairs
        for all possible config files in the site-wide config dir and user config dir combined
        """

        res = mock_util.config.files
        expected_output = [
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/uoft-tools/shared.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.toml",
                uoft_core.File.creatable,
            ),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path
            assert expected_state == actual_state

        assert "Caching list of config files" in caplog.text

    def test_config_files_env_vars(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        """
        `{app name}_SITE_CONFIG` and `{app name}_USER_CONFIG` environment variables
        should override default site and user config directories if present.

        """

        mocker.patch.dict(
            "os.environ",
            {
                "EXAMPLE_APP_SITE_CONFIG": str(
                    mock_util.mock_folders.site_config_env.dir
                ),
                "EXAMPLE_APP_USER_CONFIG": str(
                    mock_util.mock_folders.user_config_env.dir
                ),
            },
        )

        res = mock_util.config.files
        expected_output = [
            (mock_util.mock_folders.root / "etc/alternate/shared.ini", uoft_core.File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.yaml", uoft_core.File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.json", uoft_core.File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.toml", uoft_core.File.creatable),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/uoft-tools/shared.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.toml",
                uoft_core.File.creatable,
            ),
            (mock_util.mock_folders.root / "home/alternate/shared.ini", uoft_core.File.creatable),
            (
                mock_util.mock_folders.root / "home/alternate/shared.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/shared.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/shared.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.toml",
                uoft_core.File.creatable,
            ),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path
            assert expected_state == actual_state

        assert (
            f"Using {mock_util.mock_folders.site_config_env.dir} as site config directory"
            in caplog.text
        )
        assert (
            f"Using {mock_util.mock_folders.user_config_env.dir} as user config directory"
            in caplog.text
        )

    def test_config_files_states(self, mock_util: "MockedUtil"):

        # set up the file permissions
        mock_util.mock_folders.site_config.dir.chmod(0o444)
        mock_util.mock_folders.user_config.json_file.touch(0o444)
        mock_util.mock_folders.user_config.toml_file.touch(0o666)

        res = mock_util.config.files
        expected_output = [
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.ini",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.yaml",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.json",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/shared.toml",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.ini",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.yaml",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.json",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/uoft-tools/example_app.toml",
                uoft_core.File.unusable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/uoft-tools/shared.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.json",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/shared.toml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.ini",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.yaml",
                uoft_core.File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.json",
                uoft_core.File.readable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/uoft-tools/example_app.toml",
                uoft_core.File.writable,
            ),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path and expected_state == actual_state

    def test_get_config_file(self, mock_util: "MockedUtil"):
        # Test the failure condition
        with pytest.raises(uoft_core.UofTCoreError) as exc_info:
            mock_util.config.get_file_or_fail()
        assert "Could not find a valid config file" in exc_info.value.args[0]

        # Test the success conditions
        mock_util.mock_folders.user_config.toml_file.touch()
        mock_util._clear_caches()  # noqa
        file = mock_util.config.get_file_or_fail()
        assert file.exists()

    def test_get_config_file_env_var(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        # test the *_CONFIG_FILE env var
        test_file = mock_util.mock_folders.root / "test.ini"
        test_file.write_text(" ")
        mocker.patch.dict("os.environ", {"EXAMPLE_APP_CONFIG_FILE": str(test_file)})

        result = mock_util.config.get_file_or_fail()

        assert result.exists()
        assert f"Skipping normal config file lookup, using {test_file} as configuration file"

    def test_merged_config_data_ini(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.ini_file.write_text(
            uoft_core.txt(
                """
            [_common_]
            key1 = val1
            key2 = val2
            [extra]
            key = value
            """,
            )
        )
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2", "extra": {"key": "value"}}

    def test_merged_config_data_json(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.json_file.write_text(
            uoft_core.txt(
                """
            {
                "key1": "val1", 
                "key2": "val2"
            }
            """,
            )
        )
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_toml(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.toml_file.write_text(
            uoft_core.txt(
                """
            key1 = 'val1'
            key2 = 'val2'
            """,
            )
        )
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_yaml(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.yaml_file.write_text(
            uoft_core.txt(
                """
            key1: val1
            key2: val2
            """,
            )
        )
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_multi(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        # FIXME: This test is unimplemented.
        pass

    def test_get_config_key(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):  # sourcery skip: extract-duplicate-method

        # test config file missing
        with pytest.raises(uoft_core.UofTCoreError):
            mock_util.config.get_key_or_fail("key1")

        # test key missing from config file
        mock_util._clear_caches()  # noqa
        mock_util.mock_folders.user_config.json_file.write_text('{"key2": "val2"}')
        with pytest.raises(KeyError):
            mock_util.config.get_key_or_fail("key1")

        # test the happy path
        mock_util._clear_caches()  # noqa
        mock_util.mock_folders.user_config.json_file.write_text(
            '{"key1": "val1", "key2": "val2"}'
        )
        result = mock_util.config.get_key_or_fail("key1")
        assert result == "val1"

        # test env var
        mock_util._clear_caches()  # noqa
        mocker.patch.dict("os.environ", {"EXAMPLE_APP_KEY1": "env var value"})
        result = mock_util.config.get_key_or_fail("key1")
        assert result == "env var value"

    def test_get_cache_dir(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):

        # if both user and site caches exist, prefer site cache
        assert mock_util.mock_folders.site_cache.exists()
        assert mock_util.mock_folders.user_cache.exists()
        assert mock_util.cache_dir == mock_util.mock_folders.site_cache

    def test_get_cache_dir_user(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):

        # if site cache is unavailable, return user cache
        mock_util.mock_folders.site_cache.rmdir()
        mock_util.mock_folders.site_cache.parent.chmod(0o444)
        assert mock_util.mock_folders.user_cache.exists()
        assert mock_util.cache_dir == mock_util.mock_folders.user_cache

    def test_get_cache_dir_site_env(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):

        # if both user and site caches exist, prefer site cache
        mocker.patch.dict(
            "os.environ",
            {"EXAMPLE_APP_SITE_CACHE": mock_util.mock_folders.site_cache_env.__str__()},
        )
        assert mock_util.cache_dir == mock_util.mock_folders.site_cache_env

    def test_get_cache_dir_user_env(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):

        # if site cache is unavailable, return user cache
        mock_util.mock_folders.site_cache.rmdir()
        mock_util.mock_folders.site_cache.parent.chmod(0o444)
        mocker.patch.dict(
            "os.environ",
            {"EXAMPLE_APP_SITE_CACHE": mock_util.mock_folders.user_cache_env.__str__()},
        )
        assert mock_util.cache_dir == mock_util.mock_folders.user_cache_env

    @pytest.mark.skip("Not implemented yet")
    def test_logging(self):
        # FIXME: This test is unimplemented.
        raise NotImplementedError


class NestedData:

    def unstructure(self):
        input_data = {
            "menu": {
                "header": "SVG Viewer",
                "items": [
                    {"id": "Open"},
                    {"id": "OpenNew", "label": "Open New"},
                    None,
                    {"id": "ZoomIn", "label": "Zoom In"},
                    {"id": "ZoomOut", "label": "Zoom Out"},
                    {"id": "OriginalView", "label": "Original View"},
                    None,
                    {"id": "Quality"},
                    {"id": "Pause"},
                    {"id": "Mute"},
                    None,
                    {"id": "Find", "label": "Find..."},
                    {"id": "FindAgain", "label": "Find Again"},
                    {"id": "Copy"},
                    {"id": "CopyAgain", "label": "Copy Again"},
                    {"id": "CopySVG", "label": "Copy SVG"},
                    {"id": "ViewSVG", "label": "View SVG"},
                    {"id": "ViewSource", "label": "View Source"},
                    {"id": "SaveAs", "label": "Save As"},
                    None,
                    {"id": "Help"},
                    {"id": "About", "label": "About Adobe CVG Viewer..."},
                ],
                "other": {"[key1]": True, "[key2]": False},
            }
        }
        expected_output = [
            ("menu.header", "SVG Viewer"),
            ("menu.items.[0].id", "Open"),
            ("menu.items.[1].id", "OpenNew"),
            ("menu.items.[1].label", "Open New"),
            ("menu.items.[2]", None),
            ("menu.items.[3].id", "ZoomIn"),
            ("menu.items.[3].label", "Zoom In"),
            ("menu.items.[4].id", "ZoomOut"),
            ("menu.items.[4].label", "Zoom Out"),
            ("menu.items.[5].id", "OriginalView"),
            ("menu.items.[5].label", "Original View"),
            ("menu.items.[6]", None),
            ("menu.items.[7].id", "Quality"),
            ("menu.items.[8].id", "Pause"),
            ("menu.items.[9].id", "Mute"),
            ("menu.items.[10]", None),
            ("menu.items.[11].id", "Find"),
            ("menu.items.[11].label", "Find..."),
            ("menu.items.[12].id", "FindAgain"),
            ("menu.items.[12].label", "Find Again"),
            ("menu.items.[13].id", "Copy"),
            ("menu.items.[14].id", "CopyAgain"),
            ("menu.items.[14].label", "Copy Again"),
            ("menu.items.[15].id", "CopySVG"),
            ("menu.items.[15].label", "Copy SVG"),
            ("menu.items.[16].id", "ViewSVG"),
            ("menu.items.[16].label", "View SVG"),
            ("menu.items.[17].id", "ViewSource"),
            ("menu.items.[17].label", "View Source"),
            ("menu.items.[18].id", "SaveAs"),
            ("menu.items.[18].label", "Save As"),
            ("menu.items.[19]", None),
            ("menu.items.[20].id", "Help"),
            ("menu.items.[21].id", "About"),
            ("menu.items.[21].label", "About Adobe CVG Viewer..."),
            ("menu.other.[key1]", True),
            ("menu.other.[key2]", False),
        ]

        output = []
        for keypath, value in uoft_core.NestedData.unstructure(input_data):
            assert isinstance(keypath, str)
            output.append((keypath, value))
        assert output == expected_output

    def restructure(self):
        input_data = [
            ("menu.header", "SVG Viewer"),
            ("menu.items.[0].id", "Open"),
            ("menu.items.[1].id", "OpenNew"),
            ("menu.items.[1].label", "Open New"),
            ("menu.items.[2]", None),
            ("menu.items.[3].id", "ZoomIn"),
            ("menu.items.[3].label", "Zoom In"),
            ("menu.items.[4].id", "ZoomOut"),
            ("menu.items.[4].label", "Zoom Out"),
            ("menu.items.[5].id", "OriginalView"),
            ("menu.items.[5].label", "Original View"),
            ("menu.items.[6]", None),
            ("menu.items.[7].id", "Quality"),
            ("menu.items.[8].id", "Pause"),
            ("menu.items.[9].id", "Mute"),
            ("menu.items.[10]", None),
            ("menu.items.[11].id", "Find"),
            ("menu.items.[11].label", "Find..."),
            ("menu.items.[12].id", "FindAgain"),
            ("menu.items.[12].label", "Find Again"),
            ("menu.items.[13].id", "Copy"),
            ("menu.items.[14].id", "CopyAgain"),
            ("menu.items.[14].label", "Copy Again"),
            ("menu.items.[15].id", "CopySVG"),
            ("menu.items.[15].label", "Copy SVG"),
            ("menu.items.[16].id", "ViewSVG"),
            ("menu.items.[16].label", "View SVG"),
            ("menu.items.[17].id", "ViewSource"),
            ("menu.items.[17].label", "View Source"),
            ("menu.items.[18].id", "SaveAs"),
            ("menu.items.[18].label", "Save As"),
            ("menu.items.[19]", None),
            ("menu.items.[20].id", "Help"),
            ("menu.items.[21].id", "About"),
            ("menu.items.[21].label", "About Adobe CVG Viewer..."),
            ("menu.other.[key1]", True),
            ("menu.other.[key2]", False),
        ]
        expected_output = {
            "menu": {
                "header": "SVG Viewer",
                "items": [
                    {"id": "Open"},
                    {"id": "OpenNew", "label": "Open New"},
                    None,
                    {"id": "ZoomIn", "label": "Zoom In"},
                    {"id": "ZoomOut", "label": "Zoom Out"},
                    {"id": "OriginalView", "label": "Original View"},
                    None,
                    {"id": "Quality"},
                    {"id": "Pause"},
                    {"id": "Mute"},
                    None,
                    {"id": "Find", "label": "Find..."},
                    {"id": "FindAgain", "label": "Find Again"},
                    {"id": "Copy"},
                    {"id": "CopyAgain", "label": "Copy Again"},
                    {"id": "CopySVG", "label": "Copy SVG"},
                    {"id": "ViewSVG", "label": "View SVG"},
                    {"id": "ViewSource", "label": "View Source"},
                    {"id": "SaveAs", "label": "Save As"},
                    None,
                    {"id": "Help"},
                    {"id": "About", "label": "About Adobe CVG Viewer..."},
                ],
                "other": {"[key1]": True, "[key2]": False},
            }
        }
        output = uoft_core.NestedData.restructure(input_data)
        assert output == expected_output

    def remap(self):
        keymap = [
            # basic renaming
            ("menu.header", "menu.footer"),
            # renaming with shell-style wildcards
            ("menu.items.[1].*", "menu.items.[1].new*"),
            # multiple rules can be applied to the same items, will be applied in order
            ("menu.items.*", "menu.newitems.*"),
            # support multiple wildcards
            ("menu.*.[3].*", "menu.*.[3].*altered"),
            # can move entire branches of the tree around, reattach them to other parts of the tree
            ("menu.newitems.[4].*", "menu.newsubkey.*"),
        ]
        input_data = {
            "menu": {
                "header": "SVG Viewer",
                "items": [
                    {"id": "Open"},
                    {"id": "OpenNew", "label": "Open New"},
                    None,
                    {"id": "ZoomIn", "label": "Zoom In"},
                    {"id": "ZoomOut", "label": "Zoom Out"},
                ],
                "other": {"[key1]": True, "[key2]": False},
            }
        }
        expected_output = {
            "menu": {
                "footer": "SVG Viewer",
                "newitems": [
                    {"id": "Open"},
                    {"newid": "OpenNew", "newlabel": "Open New"},
                    None,
                    {"idaltered": "ZoomIn", "labelaltered": "Zoom In"},
                ],
                "newsubkey": {"id": "ZoomOut", "label": "Zoom Out"},
                "other": {"[key1]": True, "[key2]": False},
            }
        }
        unstructured = uoft_core.NestedData.unstructure(input_data)
        unstructured = uoft_core.NestedData.remap(unstructured, keymap)
        output = uoft_core.NestedData.restructure(unstructured)
        assert output == expected_output

    def filter(self):
        input_data = {
            "menu": {
                "header": "SVG Viewer",
                "items": [
                    {"id": "Open"},
                    {"id": "OpenNew", "label": "Open New"},
                    None,
                    {"id": "ZoomIn", "label": "Zoom In"},
                    {"id": "ZoomOut", "label": "Zoom Out"},
                    {"id": "OriginalView", "label": "Original View"},
                    None,
                    {"id": "Quality"},
                    {"id": "Pause"},
                    {"id": "Mute"},
                    None,
                    {"id": "Find", "label": "Find..."},
                    {"id": "FindAgain", "label": "Find Again"},
                    {"id": "Copy"},
                    {"id": "CopyAgain", "label": "Copy Again"},
                    {"id": "CopySVG", "label": "Copy SVG"},
                    {"id": "ViewSVG", "label": "View SVG"},
                    {"id": "ViewSource", "label": "View Source"},
                    {"id": "SaveAs", "label": "Save As"},
                    None,
                    {"id": "Help"},
                    {"id": "About", "label": "About Adobe CVG Viewer..."},
                ],
                "other": {
                    "first": {"id": "Help"},
                    "second": {"id": "Help"},
                },
            }
        }
        filters = [
            "menu.header",  # full match
            "menu.other.first",  # partial match
            "menu.items.*.*",  # regex match, filter out all entries in items which don't have an id
        ]
        expected_output = {
            "menu": {
                "header": "SVG Viewer",
                "items": [
                    {"id": "Open"},
                    {"id": "OpenNew", "label": "Open New"},
                    {"id": "ZoomIn", "label": "Zoom In"},
                    {"id": "ZoomOut", "label": "Zoom Out"},
                    {"id": "OriginalView", "label": "Original View"},
                    {"id": "Quality"},
                    {"id": "Pause"},
                    {"id": "Mute"},
                    {"id": "Find", "label": "Find..."},
                    {"id": "FindAgain", "label": "Find Again"},
                    {"id": "Copy"},
                    {"id": "CopyAgain", "label": "Copy Again"},
                    {"id": "CopySVG", "label": "Copy SVG"},
                    {"id": "ViewSVG", "label": "View SVG"},
                    {"id": "ViewSource", "label": "View Source"},
                    {"id": "SaveAs", "label": "Save As"},
                    {"id": "Help"},
                    {"id": "About", "label": "About Adobe CVG Viewer..."},
                ],
                "other": {"first": {"id": "Help"}},
            }
        }

        unstructured = uoft_core.NestedData.unstructure(input_data)
        filtered = uoft_core.NestedData.filter_(unstructured, filters)
        output = uoft_core.NestedData.restructure(filtered)
        assert output == expected_output
