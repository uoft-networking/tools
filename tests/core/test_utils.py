# pylint: disable=unused-argument
from pathlib import Path
import time
from typing import TYPE_CHECKING

from utsc.core import UTSCCoreError, __version__, File, Timeit, txt, lst, chomptxt

import pytest

if TYPE_CHECKING:
    from .. import MockedUtil
    from pytest_mock import MockerFixture
    from _pytest.logging import LogCaptureFixture


def test_version():
    assert isinstance(__version__, str)


def test_txt():
    res = txt(
        """
        one
        two
        three
        """
    )
    assert res == "one\ntwo\nthree\n"


def test_chomptxt():
    res = chomptxt(
        """
        one
        two
        three
        """
    )
    assert res == "one two three"

    res = chomptxt(
        """
        one

        two
        three
        """
    )
    assert res == "one\ntwo three"


def test_lst():
    res = lst(
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

    assert File.is_creatable(creatable)
    assert File.state(creatable) == File.creatable

    assert File.is_readable(readable)
    assert File.state(readable) == File.readable

    assert File.is_writable(writable)
    assert File.state(writable) == File.writable

    assert File.state(unusable) == File.unusable

    for f in tmp_path.rglob("*"):
        f.chmod(0o777)  # restore perms so the tmp_path can be cleaned up


def test_timeit():
    # the clock starts as soon as the class is initialized
    timer = Timeit()
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


class TestUtil:
    def test_config_files(self, mock_util: "MockedUtil", caplog: "LogCaptureFixture"):
        """
        the `config_files` property of the `Util` class should return a list of (path, state) pairs
        for all possible config files in the site-wide config dir and user config dir combined
        """

        res = mock_util.config.files
        expected_output = [
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/utsc-tools/shared.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.toml",
                File.creatable,
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
            (mock_util.mock_folders.root / "etc/alternate/shared.ini", File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.yaml", File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.json", File.creatable),
            (mock_util.mock_folders.root / "etc/alternate/shared.toml", File.creatable),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "etc/alternate/example_app.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/utsc-tools/shared.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.toml",
                File.creatable,
            ),
            (mock_util.mock_folders.root / "home/alternate/shared.ini", File.creatable),
            (
                mock_util.mock_folders.root / "home/alternate/shared.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/shared.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/shared.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root / "home/alternate/example_app.toml",
                File.creatable,
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
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.ini",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.yaml",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.json",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/shared.toml",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.ini",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.yaml",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.json",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "etc/xdg/utsc-tools/example_app.toml",
                File.unusable,
            ),
            (
                mock_util.mock_folders.root / "home/user/.config/utsc-tools/shared.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.json",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/shared.toml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.ini",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.yaml",
                File.creatable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.json",
                File.readable,
            ),
            (
                mock_util.mock_folders.root
                / "home/user/.config/utsc-tools/example_app.toml",
                File.writable,
            ),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path and expected_state == actual_state

    def test_get_config_file(self, mock_util: "MockedUtil"):
        # Test the failure condition
        with pytest.raises(UTSCCoreError) as exc_info:
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
        mock_util.mock_folders.user_config.ini_file.write_text(txt(
            """
            [_common_]
            key1 = val1
            key2 = val2
            [extra]
            key = value
            """,
        ))
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2", "extra": {"key": "value"}}

    def test_merged_config_data_json(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.json_file.write_text(txt(
            """
            {
                "key1": "val1", 
                "key2": "val2"
            }
            """,
        ))
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_toml(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.toml_file.write_text(txt(
            """
            key1 = 'val1'
            key2 = 'val2'
            """,
        ))
        result = mock_util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_yaml(
        self,
        mock_util: "MockedUtil",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        mock_util.mock_folders.user_config.yaml_file.write_text(txt(
            """
            key1: val1
            key2: val2
            """,
        ))
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
        with pytest.raises(UTSCCoreError):
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
