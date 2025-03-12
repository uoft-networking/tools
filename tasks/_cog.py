"""Utility functions and code generators for the cog command."""

import importlib
from pathlib import Path

try:
    import cog
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
    module = importlib.import_module(module_path)
    try:
        from uoft_core import BaseSettings
    except ImportError:
        from typing import Any as BaseSettings
    settings: BaseSettings = getattr(module, class_name)
    for name, field in settings.__fields__.items():
        title = field.field_info.title or ''
        desc = field.field_info.description or ''
        default = field.default or ''
        cog.outl(f"\
        | {name} | {field.type_.__name__} | {title} | {desc} | {default} |")


def all_projects_as_python_list():
    "Generate a list of all projects in the uoft-* namespace."
    cog.outl("ALL_PROJECTS = [")
    for p in Path('projects').iterdir():
        if not p.is_dir():
            continue
        cog.outl(f'    "{p.name}",')
    cog.outl("]")


def all_projects_as_dependencies():
    "Generate a list of all projects in the uoft-* namespace as dependencies."
    for p in Path('projects').iterdir():
        if not p.is_dir():
            continue
        cog.outl(f'    "uoft-{p.name}",')
    for p in Path('custom-forks').iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith('_'):
            continue
        cog.outl(f'    "{p.name}",')


def all_projects_as_uv_sources():
    "Generate a list of all projects in the uoft-* namespace as uv sources."
    for p in Path('projects').iterdir():
        if not p.is_dir():
            continue
        cog.outl(f'uoft-{p.name} = {{ workspace = true }}')
    for p in Path('custom-forks').iterdir():
        if not p.is_dir():
            continue
        cog.outl(f'{p.name} = {{ workspace = true }}')

def lazy_import(source):
    """given a block of python import statements, generate a block of lazy imports"""
    from textwrap import dedent
    from ast import parse, unparse, Import, ImportFrom

    def txt(s):
        return dedent(s.lstrip("\n"))
    
    def construct_dotted_import_class_tree(alias):
        # ex import package.sub.module
        # This requires special handling, since we need to make a container tree for the import
        parts = alias.name.split('.')
        
        # Create the root class for the package
        # at ever level, container_tree will be the class for that level
        # root_class remains the top level class
        root_class = parse(f"class {parts[0]}: pass").body[0]
        container_tree = root_class
        del container_tree.body[0] # remove the pass statement
        current_parts = []

        # Build nested classes for each package level
        for i, part in enumerate(parts[1:], 1):
            current_parts.append(parts[i-1])
            
            if i < len(parts) - 1:
                # Create nested container class
                nested_class = parse(f"class {part}: pass").body[0]
                del nested_class.body[0] # remove the pass statement
                container_tree.body.append(nested_class)
                container_tree = nested_class
            else:
                # For the final module part, add as a static method
                method_ast = parse(txt(f"""
                    @staticmethod
                    @lazyobject
                    def {part}():
                        print('importing {alias.name}')
                        import {alias.name}
                        return {alias.name}
                    """)).body[0]
                container_tree.body.append(method_ast)
        return root_class

    source = txt(source)
    tree = parse(source)
    new_tree = parse(txt("""
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            pass
        else:
            from lazyasd import lazyobject
        """))
    standard_imports: list = new_tree.body[1].body # type: ignore
    lazy_imports: list = new_tree.body[1].orelse # type: ignore

    del standard_imports[0] # remove the pass statement

    for node in tree.body:
        standard_imports.append(node)
        if isinstance(node, Import):
            for alias in node.names:
                if '.' in alias.name and not alias.asname:
                    lazy_imports.append(construct_dotted_import_class_tree(alias))

                else:
                    asname = alias.asname or alias.name
                    lazy_imports.append(parse(txt(f"""
                        @lazyobject
                        def {asname}():
                            print('importing {alias.name}')
                            import {alias.name}
                            return {alias.name}
                        """)).body[0])
        elif isinstance(node, ImportFrom):
            for alias in node.names:
                asname = alias.asname or alias.name
                module = node.module or '.'
                module_log_str = f"{module}.{alias.name}" if module != '.' else f".{alias.name}"
                lazy_imports.append(parse(txt(f"""
                    @lazyobject
                    def {asname}():
                        print('importing {module_log_str}')
                        from {module} import {alias.name}
                        return {alias.name}
                    """)).body[0])
    cog.outl(unparse(new_tree))

if __name__ == "__main__":
    # test lazy_imports
    lazy_import("""
        # LazyLoad
        from typing import (
            Any,
            Callable,
            ClassVar,
            Dict,
            List,
            Optional,
            Type,
            TypeVar,
            get_args,
            get_origin,
        )
        import inspect
        from shutil import which
        from importlib.metadata import version
        from subprocess import CalledProcessError, run

        from pydantic import BaseSettings as PydanticBaseSettings, Extra, root_validator
        import pydantic.types
        import pydantic.validators.BaseValidator

        from . import logging
        from .types import StrEnum, SecretStr
        from ._vendor.decorator import decorate
        """)
