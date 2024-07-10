# helper macros go here
from textwrap import dedent
import logging
from ast import parse

import task_runner

from mcpyrate.quotes import macros, q, u, a, n, h  # noqa: F401 # type: ignore
from mcpyrate import unparse, dump

logger = logging.getLogger(__name__)


def coco_compile(tree, **kw):
    """[syntax, decorator] Compile a coconut function to python"""
    # skip compilation if we're in a shell auto-completion context
    # shell autocomplete doesn't need to know anything about a function's body to work, it only needs
    # to know the function's signature, which we're not modifying
    if task_runner._in_completion_context():
        return tree

    from coconut.api import parse as parse_coco

    cococ_src: str = tree.body[0].value.value
    compiled_py_src: str = parse_coco(dedent(cococ_src), "block")
    coco_tree = parse(compiled_py_src)
    tree.body = coco_tree.body
    logger.debug(unparse(tree))
    return tree


def lazy_imports(stmts, **kw):
    """[syntax, block] Import modules lazily

    convert:
        ```python
        with lazy_imports:
            import foo
            import bar
        ```
    to:
        ```python
        from typing import TYPE_CHECKING
        from lazyasd import lazyobject
        if TYPE_CHECKING:
            import foo
            import bar
        else:
            @lazyobject
            def foo():
                print('importing foo')
                import foo
                return foo
            @lazyobject
            def bar():
                print('importing bar')
                import bar
                return bar
        ```
    """
    if task_runner._in_completion_context():
        return stmts

    logger.debug(unparse(stmts, debug=True))
    logger.debug(dump(stmts))
    raise NotImplementedError("lazy_imports is not implemented yet")

def zxpy(stmts, **kw):
    """[syntax, block] Run python code in a shell

    inspired by https://github.com/tusharsadhwani/zxpy
    
    convert:
        ```python
        with zxpy:
            my_branch = 'main'
            ~'echo hello'
            ~f'git fetch origin {my_branch}'
            stdout = ~'git rev-parse --abbrev-ref HEAD'
            stdout, stderr, return_code = ~'git rev-parse --abbrev-ref HEAD'
        ```
    to:
        ```python
        my_branch = 'main'
        run('echo hello')
        run(f'git fetch origin {my_branch}')
        stdout = run('git rev-parse --abbrev-ref HEAD', cap=True)
        _result = run('git rev-parse --abbrev-ref HEAD')
        stdout, stderr, return_code = _result.stdout, _result.stderr, _result.returncode
        ```
    """
    if task_runner._in_completion_context():
        return stmts

    import ast

    logger.debug("zxpy: before")
    logger.debug(unparse(stmts))
    logger.debug(dump(stmts))

    def is_zx_str(node):
        return (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Invert)
            and isinstance(node.operand, (ast.Constant, ast.JoinedStr))
        )
    
    def run_call(value, cap=False, cap_all=False):
        return q[run(a[value], cap=u[cap], capture_output=u[cap_all])]

    new_stmts = []

    for stmt in stmts:
        if isinstance(stmt, ast.Expr) and is_zx_str(stmt.value):
            stmt.value = run_call(stmt.value.operand)
            new_stmts.append(stmt)

        elif isinstance(stmt, ast.Assign) and is_zx_str(stmt.value):
            if isinstance(stmt.targets[0], ast.Name):
                # we're dealing with a `stdout = ~'...'` case
                stmt.value = run_call(stmt.value.operand, cap=True)
                new_stmts.append(stmt)
            else:
                # we're dealing with the `stdout, stderr, return_code = ~'...'` case
                with q as quoted:
                    _result = a[run_call(stmt.value.operand, cap_all=True)]
                    stdout, stderr, return_code = _result.stdout.strip(), _result.stderr.strip(), _result.returncode
                new_stmts.extend(quoted)
        else:
            new_stmts.append(stmt)

    logger.debug("zxpy: after")
    logger.debug(unparse(new_stmts))
    logger.debug(dump(new_stmts))

    return new_stmts
