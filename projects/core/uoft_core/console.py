_CONSOLE = None
def console():
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
