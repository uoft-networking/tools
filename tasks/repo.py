from pathlib import Path

from task_runner import run, REPO_ROOT

from . import all_projects_by_name



def cog_files():
    "Run cog against all cog files in the repo"
    run(f"cog -r -I {REPO_ROOT}/tasks/ projects/*/README.md projects/core/uoft_core/__main__.py")



def update_pyproject_build_hooks():
    """update all pyproject.py build hooks"""
    for project in all_projects_by_name():
        print(f"updating build hook for {project}")
        run(f"cp tasks/_new_project/template/pyproject.py projects/{project}/pyproject.py")


def debug_pydantic(undo: bool = False):
    """disable pydantic compiled modules in virtualenv so we can step through the python code"""
    if undo:
        for ext in Path(".venv").glob(
            "lib/python*/site-packages/pydantic/*.cpython-*.so.disabled"
        ):
            print(f"renaming {ext.name} to {ext.with_suffix('').name}")
            ext.rename(ext.with_suffix(""))
    else:
        for ext in Path(".venv").glob("lib/python*/site-packages/pydantic/*.so"):
            print(f"renaming {ext.name} to {ext.with_suffix('.so.disabled').name}")
            ext.rename(ext.with_suffix(".so.disabled"))
