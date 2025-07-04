from pathlib import Path

from task_runner import run, REPO_ROOT

from . import all_projects_by_name, run_cog

from ._macros import macros, zxpy  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType] # noqa: F401


def cog_files():
    "Run cog against all cog files in the repo"
    run_cog(
        "projects/*/README.md projects/core/uoft_core/tests/*.py "
        "projects/*/uoft_*/__main__.py projects/*/uoft_*/cli.py pyproject.toml"
    )


def update_pyproject_build_hooks():
    """update all pyproject.py build hooks"""
    for project in all_projects_by_name():
        print(f"updating build hook for {project}")
        run(f"cp tasks/_new_project/template/pyproject.py projects/{project}/pyproject.py")


def debug_pydantic(undo: bool = False):
    """disable pydantic compiled modules in virtualenv so we can step through the python code"""
    if undo:
        for ext in Path(".venv").glob("lib/python*/site-packages/pydantic/*.cpython-*.so.disabled"):
            print(f"renaming {ext.name} to {ext.with_suffix('').name}")
            ext.rename(ext.with_suffix(""))
    else:
        for ext in Path(".venv").glob("lib/python*/site-packages/pydantic/*.so"):
            print(f"renaming {ext.name} to {ext.with_suffix('.so.disabled').name}")
            ext.rename(ext.with_suffix(".so.disabled"))


def lock():
    """update the monorepo uv lock file"""
    run("uv lock --refresh")
