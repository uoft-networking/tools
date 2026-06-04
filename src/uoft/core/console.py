from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

_CONSOLE = None
_STDOUT_CONSOLE = None
def console(stderr: bool = True) -> "Console":
    "a global on-demand console instance"
    # note to future me: If you're wondering why console is a global var instead of a thread local,
    # Console is thread safe, so it's better to have only one console instance managing sys.stderr for the whole program
    global _CONSOLE
    if _CONSOLE is None:
        from rich.console import Console
        from rich.theme import Theme
        from rich.style import Style

        _CONSOLE = Console(
            stderr=True,
            theme=Theme(
                {
                    "logging.level.debug": Style(color="yellow"),
                    "logging.level.trace": Style(color="magenta"),
                    "logging.level.success": Style(color="green"),
                }
            ),
        )
    return _CONSOLE

def stdout_console() -> "Console":
    "a global on-demand console instance that prints to stdout instead of stderr"
    # note to future me: If you're wondering why console is a global var instead of a thread local,
    # Console is thread safe, so it's better to have only one console instance managing sys.stderr for the whole program
    global _STDOUT_CONSOLE
    if _STDOUT_CONSOLE is None:
        from rich.console import Console
        from rich.theme import Theme
        from rich.style import Style

        _STDOUT_CONSOLE = Console(
            theme=Theme(
                {
                    "logging.level.debug": Style(color="yellow"),
                    "logging.level.trace": Style(color="magenta"),
                    "logging.level.success": Style(color="green"),
                }
            ),
        )
    return _STDOUT_CONSOLE
