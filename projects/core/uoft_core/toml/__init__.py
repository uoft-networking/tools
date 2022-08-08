"""A lil' TOML parser/writer."""

__all__ = ("loads", "load", "TOMLDecodeError", "dumps", "dump")
__version__ = "1.2.1"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

from ._parser import TOMLDecodeError, load, loads
from ._writer import dump, dumps
