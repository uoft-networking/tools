import logging

print("import module c")
import sys

print(sys.modules.keys())


def func():
    logging.debug("test from stdlib root logger maybe")
    log = logging.getLogger(__name__)
    log.debug("test from stdlib __name__ logger")
