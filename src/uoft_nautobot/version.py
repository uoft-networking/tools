from importlib.metadata import version

assert __package__
__version__ = version(__package__)
