# pylint: disable=unused-argument
from pathlib import Path
from typing import TYPE_CHECKING

from utsc.core import txt
from utsc.scripts import bluecat

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from .. import MockFolders


def test_bluecat(mock_folders: "MockFolders", monkeypatch: "MonkeyPatch") -> None:
    """Test bluecat."""
    bluecat.collect()
