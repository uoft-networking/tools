from loguru import logger

from . import module_b, module_c


logger.disable(__name__)
logger.debug("module a import complete")


def doathing():
    logger.trace("This is a TRACE message")
    logger.debug("This is a DEBUG message")
    logger.bind(var="val").info("Hello")
    logger.success("test <white>message</>")
    logger.warning("This is a <blue>Warning</>")
    logger.error("ohhhh bad")
    logger.critical("we're sinking captain!")
    module_b.func()
    module_c.func()


if __name__ == "__main__":
    import os

    if os.environ.get("PYDEBUG"):
        exit()
