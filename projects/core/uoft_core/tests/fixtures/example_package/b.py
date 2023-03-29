from loguru import logger
import logging

logger.disable(__name__)
logger.debug("module b loaded")


def func():
    logger.debug("hello from module b")
    logging.debug("test from stdlib root logger maybe")
    log = logging.getLogger(__name__)
    log.debug("test from stdlib __name__ logger")
