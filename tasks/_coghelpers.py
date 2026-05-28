"""Utility functions and code generators for the cog command."""

import importlib
import typing as t
from pathlib import Path

try:
    import cog  # pyright: ignore[reportMissingImports,reportAssignmentType]
except ImportError:

    class cog:
        @staticmethod
        def outl(text):
            print(text)


def gen_conf_table(module_path: str, class_name: str = "Settings"):
    "Generate a table of configuration options from a Settings class definition."
    cog.outl("""\
        | Option | Type | Title | Description | Default |
        | ------ | ---- | ----- | ----------- | ------- |""")
    try:
        from uoft.core import BaseSettings
    except ImportError:
        from typing import Any as BaseSettings
    # the settings class will be in the package's __init__.py file if it has one
    # or in {package}.conf if the package is set up as a pep420 namespace package
    try:
        module = importlib.import_module(module_path)
        settings: BaseSettings = getattr(module, class_name)
    except (ModuleNotFoundError, AttributeError):
        try:
            module = importlib.import_module(f"{module_path}.conf")
            settings: BaseSettings = getattr(module, class_name)
        except (ModuleNotFoundError, AttributeError):
            raise ImportError(f"Could not find a {class_name} class in either {module_path} or {module_path}.conf")
    for name, field in settings.__fields__.items():
        title = field.field_info.title or ""
        desc = field.field_info.description or ""
        default = field.default or ""
        cog.outl(f"\
        | {name} | {field.type_.__name__} | {title} | {desc} | {default} |")


def gen_prelude_exports():
    """
    A prelude is an importable module that imports and re-exports symbols from a bunch of different 
    modules and packages, usually as a convenience for use in scripts and REPLs. The correct way to write a 
    prelude in python is to import all the symbols you need in the prelude module, and then set that module's
     __all__ to a list of strings of the symbols you want to export. This is super tedious to write and maintain, 
     since you have to manually keep the __all__ list in sync with the actual imports, so here we automate the process
    """
    import ast
    prelude_file = cog.inFile  # pyright: ignore[reportAttributeAccessIssue]
    with open(prelude_file, "r") as f:
        tree = ast.parse(f.read())
    exports = []

    class SymbolTracker(ast.NodeVisitor):
        # ast.Import and ast.ImportFrom both expose their imported symbols as ast.alias objects
        # We don't need to walk the import nodes themselves, we can get what we need from the ast.alias objects themselves
        def visit_alias(self, node):
            if node.asname:
                exports.append(node.asname)
            else:
                name = node.name.split(".")[0]  # only export the top-level name, ex import package.sub.module would only export "package"
                exports.append(name)

        # preludes may also define and export their own symbols, so we need to track those as well
        def visit_FunctionDef(self, node):
            if node.name.startswith("_"):
                return
            exports.append(node.name)

        def visit_ClassDef(self, node):
            if node.name.startswith("_"):
                return
            exports.append(node.name)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id.startswith("_"):
                        continue
                    exports.append(target.id)

    # Walk the AST
    visitor = SymbolTracker()
    visitor.visit(tree)

    # generate the __all__ variable
    cog.outl("__all__ = [")
    for symbol in sorted(exports):
        cog.outl(f'    "{symbol}",')
    cog.outl("]")


def all_projects_as_python_list():
    "Generate a list of all projects in the uoft-* namespace."
    from . import all_projects, REPO_ROOT
    projects = []
    for p in all_projects():
        path = p.relative_to(REPO_ROOT / "src")
        path = str(path)
        if '/' in path:
            path = path.replace('/', '.')
        projects.append(path)
    cog.outl("ALL_PROJECTS = [")
    for p in projects:
        cog.outl(f'    "{p}",')
    cog.outl("]")


def lazy_import(source):
    """given a block of python import statements, generate a block of lazy imports"""
    from textwrap import dedent
    from ast import parse, unparse, Import, ImportFrom, If

    def txt(s):
        return dedent(s.lstrip("\n"))

    def construct_dotted_import_class_tree(alias):
        # ex import package.sub.module
        # This requires special handling, since we need to make a container tree for the import
        parts = alias.name.split(".")

        # Create the root class for the package
        # at ever level, container_tree will be the class for that level
        # root_class remains the top level class
        root_class = parse(f"class {parts[0]}: pass").body[0]
        container_tree = root_class
        del container_tree.body[0]  # remove the pass statement # pyright: ignore[reportAttributeAccessIssue]
        current_parts = []

        # Build nested classes for each package level
        for i, part in enumerate(parts[1:], 1):
            current_parts.append(parts[i - 1])

            if i < len(parts) - 1:
                # Create nested container class
                nested_class = parse(f"class {part}: pass").body[0]
                del nested_class.body[0]  # remove the pass statement # pyright: ignore[reportAttributeAccessIssue]
                container_tree.body.append(nested_class)  # pyright: ignore[reportAttributeAccessIssue]
                container_tree = nested_class
            else:
                # For the final module part, add as a static method
                method_ast = parse(
                    txt(f"""
                    @staticmethod
                    @lazyobject
                    def {part}():
                        print('importing {alias.name}')
                        import {alias.name}
                        return {alias.name}
                    """)
                ).body[0]
                container_tree.body.append(method_ast)  # pyright: ignore[reportAttributeAccessIssue]
        return root_class

    source = txt(source)
    tree = parse(source)
    new_tree = parse(
        txt("""
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            pass
        else:
            from lazyasd import lazyobject
        """)
    )
    if_stmt = t.cast(If, new_tree.body[1])
    standard_imports = if_stmt.body 
    lazy_imports = if_stmt.orelse

    del standard_imports[0]  # remove the pass statement

    for node in tree.body:
        standard_imports.append(node)
        if isinstance(node, Import):
            for alias in node.names:
                if "." in alias.name and not alias.asname:
                    lazy_imports.append(construct_dotted_import_class_tree(alias))

                else:
                    asname = alias.asname or alias.name
                    lazy_imports.append(
                        parse(
                            txt(f"""
                        @lazyobject
                        def {asname}():
                            print('importing {alias.name}')
                            import {alias.name}
                            return {alias.name}
                        """)
                        ).body[0]
                    )
        elif isinstance(node, ImportFrom):
            for alias in node.names:
                asname = alias.asname or alias.name
                module = node.module or "."
                module_log_str = f"{module}.{alias.name}" if module != "." else f".{alias.name}"
                lazy_imports.append(
                    parse(
                        txt(f"""
                    @lazyobject
                    def {asname}():
                        print('importing {module_log_str}')
                        from {module} import {alias.name}
                        return {alias.name}
                    """)
                    ).body[0]
                )
    cog.outl(unparse(new_tree))


def all_importable_modules():
    "Generate a list of all importable modules in the monorepo"
    from task_runner import REPO_ROOT
    cog.outl("importable_modules = [")
    for p in Path(REPO_ROOT/"src").rglob("**/*.py"):
        p = p.relative_to(REPO_ROOT / "src")
        if "tests" in p.parts:
            continue
        if "_vendor" in p.parts:
            continue
        if p == Path("src/apps"):
            continue
        parts = list(p.parent.parts)
        if p.stem != "__init__":
            parts.append(p.stem)
        r = ".".join(parts)
        cog.outl(f'    "{r}",')
    cog.outl("]")


def compute_pants_dist_deps(path: str):
    """
    Given the path to a project, compute the dependencies that should be 
    added to any pex_binary or scie_binary target for that project.
    """
    from task_runner import run, REPO_ROOT
    all_deps = run(f"pants dependencies --transitive src/{path}", cap=True).splitlines()
    resolved_deps = set()
    for dep in filter(lambda d: ':lib' in d, all_deps):
        target_dir = dep.rpartition(":")[0].rpartition("/")[0]
        if target_dir == f"src/{path}":
            # dependency on the local dist target is already 
            # automatically specified in the uoft_python_cli() macro
            continue
        resolved_deps.add(f"{target_dir}:dist")
    for dep in sorted(resolved_deps):
        cog.outl(f'        "{dep}",')


def version_expression():
    from task_runner import REPO_ROOT
    from setuptools_scm import get_version
    version = get_version(root=str(REPO_ROOT))
    cog.outl(f'__version__ = "{version}"')

def _debug():
    "debug with ./run --debug exec tasks._coghelpers:_debug"
    compute_pants_dist_deps("uoft_nautobot")
    # test lazy_imports
    # lazy_import("""
    #     # LazyLoad
    #     from typing import (
    #         Any,
    #         Callable,
    #         ClassVar,
    #         Dict,
    #         List,
    #         Optional,
    #         Type,
    #         TypeVar,
    #         get_args,
    #         get_origin,
    #     )
    #     import inspect
    
    #     from shutil import which
    #     from importlib.metadata import version
    #     from subprocess import CalledProcessError, run

    #     from pydantic.v1 import BaseSettings as PydanticBaseSettings, Extra, root_validator
    #     import pydantic.v1.types
    #     import pydantic.v1.validators.BaseValidator

    #     from . import logging
    #     from .types import StrEnum, SecretStr
    #     from ._vendor.decorator import decorate
    #     """)
