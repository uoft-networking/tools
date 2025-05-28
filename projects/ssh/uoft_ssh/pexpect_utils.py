from pexpect import spawn, EOF, TIMEOUT

from uoft_core import logging

logger = logging.getLogger(__name__)


class UofTPexpectSpawn(spawn):
    EOF = EOF
    TIMEOUT = TIMEOUT

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.multi_expect = MultiExpect(self)

    def _log(self, s, direction):
        if self.logfile is self.logfile_send is self.logfile_read is None:
            # log read to debug logger by default
            if direction == "read":
                logger.debug(f"{direction}: {s}")
        else:
            super()._log(s, direction)  # pyright: ignore[reportAttributeAccessIssue]


class MultiExpect:
    """Utility class to register functions as expect handlers"""

    def __init__(self, parent: UofTPexpectSpawn) -> None:
        self.parent = parent
        self.handlers = []
        self.timeout = -1

    def __call__(self, timeout: float | None = -1):
        "Start a new multi-expect session"
        self.clear()
        self.timeout = timeout

    def register(
        self, pattern: str | type[UofTPexpectSpawn.TIMEOUT] | type[UofTPexpectSpawn.EOF] | type[TIMEOUT] | type[EOF]
    ):
        def decorator(func):
            self.handlers.append((pattern, func))
            return func

        return decorator

    def start(self):
        "Start looking for any registered patterns, return the result of the handler for the first found pattern"
        if not self.handlers:
            raise ValueError("No handlers registered")
        patterns = [pattern for pattern, _ in self.handlers]
        res = self.parent.expect(patterns, timeout=self.timeout)
        func = self.handlers[res][1]
        return func()

    def reenter_loop(self):
        # A common pattern when implementing a state machine with MultiExpect
        # is for some handlers to call back into the loop recursively.
        # This alias method is used to make that more readable.
        # It is not strictly necessary, but it makes the code clearer.
        "Reenter the loop to start looking for registered patterns again"
        return self.start()

    def clear(self):
        self.handlers = []
        self.timeout = -1
