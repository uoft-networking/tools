# pylint: disable=unused-argument
from pathlib import Path
import time
from typing import TYPE_CHECKING

from utsc.core import UTSCCoreError, __version__, File, Timeit, txt, lst, chomptxt

import pytest

if TYPE_CHECKING:
    from .. import MockUtilFolders
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
    def test_config_files(
        self, mock_folders: "MockUtilFolders", caplog: "LogCaptureFixture"
    ):
        """
        the `config_files` property of the `Util` class should return a list of (path, state) pairs
        for all possible config files in the site-wide config dir and user config dir combined
        """
        util, folders = mock_folders

        res = util.config.files
        expected_output = [
            (folders.root / "etc/xdg/at-utils/shared.ini", File.creatable),
            (folders.root / "etc/xdg/at-utils/shared.yaml", File.creatable),
            (folders.root / "etc/xdg/at-utils/shared.json", File.creatable),
            (folders.root / "etc/xdg/at-utils/shared.toml", File.creatable),
            (folders.root / "etc/xdg/at-utils/example_app.ini", File.creatable),
            (folders.root / "etc/xdg/at-utils/example_app.yaml", File.creatable),
            (folders.root / "etc/xdg/at-utils/example_app.json", File.creatable),
            (folders.root / "etc/xdg/at-utils/example_app.toml", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.ini", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.yaml", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.json", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.toml", File.creatable),
            (
                folders.root / "home/user/.config/at-utils/example_app.ini",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.yaml",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.json",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.toml",
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
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        """
        `{app name}_SITE_CONFIG` and `{app name}_USER_CONFIG` environment variables
        should override default site and user config directories if present.

        """
        util, folders = mock_folders

        mocker.patch.dict(
            "os.environ",
            {
                "EXAMPLE_APP_SITE_CONFIG": str(folders.site_config_env.dir),
                "EXAMPLE_APP_USER_CONFIG": str(folders.user_config_env.dir),
            },
        )

        res = util.config.files
        expected_output = [
            (folders.root / "etc/alternate/shared.ini", File.creatable),
            (folders.root / "etc/alternate/shared.yaml", File.creatable),
            (folders.root / "etc/alternate/shared.json", File.creatable),
            (folders.root / "etc/alternate/shared.toml", File.creatable),
            (folders.root / "etc/alternate/example_app.ini", File.creatable),
            (folders.root / "etc/alternate/example_app.yaml", File.creatable),
            (folders.root / "etc/alternate/example_app.json", File.creatable),
            (folders.root / "etc/alternate/example_app.toml", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.ini", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.yaml", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.json", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.toml", File.creatable),
            (
                folders.root / "home/user/.config/at-utils/example_app.ini",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.yaml",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.json",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.toml",
                File.creatable,
            ),
            (folders.root / "home/alternate/shared.ini", File.creatable),
            (folders.root / "home/alternate/shared.yaml", File.creatable),
            (folders.root / "home/alternate/shared.json", File.creatable),
            (folders.root / "home/alternate/shared.toml", File.creatable),
            (folders.root / "home/alternate/example_app.ini", File.creatable),
            (folders.root / "home/alternate/example_app.yaml", File.creatable),
            (folders.root / "home/alternate/example_app.json", File.creatable),
            (folders.root / "home/alternate/example_app.toml", File.creatable),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path
            assert expected_state == actual_state

        assert (
            f"Using {folders.site_config_env.dir} as site config directory"
            in caplog.text
        )
        assert (
            f"Using {folders.user_config_env.dir} as user config directory"
            in caplog.text
        )

    def test_config_files_states(self, mock_folders: "MockUtilFolders"):
        util, folders = mock_folders

        # set up the file permissions
        folders.site_config.dir.chmod(0o444)
        folders.user_config.json_file.touch(0o444)
        folders.user_config.toml_file.touch(0o666)

        res = util.config.files
        expected_output = [
            (folders.root / "etc/xdg/at-utils/shared.ini", File.unusable),
            (folders.root / "etc/xdg/at-utils/shared.yaml", File.unusable),
            (folders.root / "etc/xdg/at-utils/shared.json", File.unusable),
            (folders.root / "etc/xdg/at-utils/shared.toml", File.unusable),
            (folders.root / "etc/xdg/at-utils/example_app.ini", File.unusable),
            (folders.root / "etc/xdg/at-utils/example_app.yaml", File.unusable),
            (folders.root / "etc/xdg/at-utils/example_app.json", File.unusable),
            (folders.root / "etc/xdg/at-utils/example_app.toml", File.unusable),
            (folders.root / "home/user/.config/at-utils/shared.ini", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.yaml", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.json", File.creatable),
            (folders.root / "home/user/.config/at-utils/shared.toml", File.creatable),
            (
                folders.root / "home/user/.config/at-utils/example_app.ini",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.yaml",
                File.creatable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.json",
                File.readable,
            ),
            (
                folders.root / "home/user/.config/at-utils/example_app.toml",
                File.writable,
            ),
        ]
        for expected, actual in zip(expected_output, res):
            expected_path, expected_state = expected
            actual_path, actual_state = actual
            assert expected_path == actual_path and expected_state == actual_state

    def test_get_config_file(self, mock_folders: "MockUtilFolders"):
        util, folders = mock_folders
        # Test the failure condition
        with pytest.raises(UTSCCoreError) as exc_info:
            util.config.get_file_or_fail()
        assert "Could not find a valid config file" in exc_info.value.args[0]

        # Test the success conditions
        folders.user_config.toml_file.touch()
        util._clear_caches()  # noqa
        file = util.config.get_file_or_fail()
        assert file.exists()

    def test_get_config_file_env_var(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders
        # test the *_CONFIG_FILE env var
        test_file = folders.root / "test.ini"
        test_file.write_text(" ")
        mocker.patch.dict("os.environ", {"EXAMPLE_APP_CONFIG_FILE": str(test_file)})

        result = util.config.get_file_or_fail()

        assert result.exists()
        assert f"Skipping normal config file lookup, using {test_file} as configuration file"

    def test_merged_config_data_ini(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders
        folders.user_config.ini_file.write_text(
            """
            [_common_]
            key1 = val1
            key2 = val2
            [extra]
            key = value
            """,
        )
        result = util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2", "extra": {"key": "value"}}

    def test_merged_config_data_json(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders
        folders.user_config.json_file.write_text(
            """
            {
                "key1": "val1", 
                "key2": "val2"
            }
            """,
        )
        result = util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_toml(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders
        folders.user_config.toml_file.write_text(
            """
            key1 = 'val1'
            key2 = 'val2'
            """,
        )
        result = util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_yaml(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders
        folders.user_config.yaml_file.write_text(
            """
            key1: val1
            key2: val2
            """,
        )
        result = util.config.merged_data
        assert result == {"key1": "val1", "key2": "val2"}

    def test_merged_config_data_multi(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        # FIXME: This test is unimplemented.
        pass

    def test_get_config_key(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):  # sourcery skip: extract-duplicate-method
        util, folders = mock_folders

        # test config file missing
        with pytest.raises(UTSCCoreError):
            util.config.get_key_or_fail("key1")

        # test key missing from config file
        util._clear_caches()  # noqa
        folders.user_config.json_file.write_text('{"key2": "val2"}')
        with pytest.raises(KeyError):
            util.config.get_key_or_fail("key1")

        # test the happy path
        util._clear_caches()  # noqa
        folders.user_config.json_file.write_text('{"key1": "val1", "key2": "val2"}')
        result = util.config.get_key_or_fail("key1")
        assert result == "val1"

        # test env var
        util._clear_caches()  # noqa
        mocker.patch.dict("os.environ", {"EXAMPLE_APP_KEY1": "env var value"})
        result = util.config.get_key_or_fail("key1")
        assert result == "env var value"

    def test_get_cache_dir(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders

        # if both user and site caches exist, prefer site cache
        assert folders.site_cache.exists()
        assert folders.user_cache.exists()
        assert util.cache_dir == folders.site_cache

    def test_get_cache_dir_user(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders

        # if site cache is unavailable, return user cache
        folders.site_cache.rmdir()
        folders.site_cache.parent.chmod(0o444)
        assert folders.user_cache.exists()
        assert util.cache_dir == folders.user_cache

    def test_get_cache_dir_site_env(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders

        # if both user and site caches exist, prefer site cache
        mocker.patch.dict(
            "os.environ", {"EXAMPLE_APP_SITE_CACHE": folders.site_cache_env.__str__()}
        )
        assert util.cache_dir == folders.site_cache_env

    def test_get_cache_dir_user_env(
        self,
        mock_folders: "MockUtilFolders",
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture",
    ):
        util, folders = mock_folders

        # if site cache is unavailable, return user cache
        folders.site_cache.rmdir()
        folders.site_cache.parent.chmod(0o444)
        mocker.patch.dict(
            "os.environ", {"EXAMPLE_APP_SITE_CACHE": folders.user_cache_env.__str__()}
        )
        assert util.cache_dir == folders.user_cache_env

    @pytest.mark.skip("Not implemented yet")
    def test_logging(self):
        # FIXME: This test is unimplemented.
        raise NotImplementedError


