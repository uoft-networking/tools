from pexpect import spawn, EOF, TIMEOUT

from uoft_core import logging

logger = logging.getLogger(__name__)

class UofTPexpectSpawn(spawn):
    EOF = EOF
    TIMEOUT = TIMEOUT

    def __init__(self, *args, **kwargs, ):
        super().__init__(*args, **kwargs)
        self.multi_expect = MultiExpect(self)

    def _log(self, s, direction):
        if self.logfile is self.logfile_send is self.logfile_read is None:
            # log read to debug logger by default
            if direction == 'read':
                logger.debug(f"{direction}: {s}")
        else:
            super()._log(s, direction)  # pyright: ignore[reportAttributeAccessIssue]


class MultiExpect:
    """Utility class to register functions as expect handlers"""

    def __init__(self, parent: UofTPexpectSpawn) -> None:
        self.parent = parent
        self.handlers = []

    def register(self, pattern: str|type[TIMEOUT]|type[EOF]):
        def decorator(func):
            self.handlers.append((pattern, func))
            return func

        return decorator

    def start(self):
        patterns = [pattern for pattern, _ in self.handlers]
        res = self.parent.expect(patterns)
        func = self.handlers[res][1]
        return func()

    def clear(self):
        self.handlers = []
