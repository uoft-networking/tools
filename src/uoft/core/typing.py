"""typing utilities and extensions to the stdlib typing module."""

from typing import TypeVar, ParamSpec, Callable, Any, cast

T = TypeVar("T")
P = ParamSpec("P")


def params_of(_: Callable[P, Any]) -> Callable[[Callable[..., T]], Callable[P, T]]:
    """
    Type-checker utility decorator informs type checkers that
    your function has the same parameters as the decorated function.

    Example:
    """
    # note this utility may end up in the stdlib, see https://github.com/python/cpython/issues/107001
    # note this utility may become obsolete 

    def return_func(func: Callable[..., T]) -> Callable[P, T]:
        return cast(Callable[P, T], func)

    return return_func
