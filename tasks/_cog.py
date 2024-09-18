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
