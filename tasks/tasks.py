"""top-level tasks for the monorepo"""

import os
from typing import Annotated, Optional, no_type_check
from textwrap import dedent
from tempfile import TemporaryDirectory
from pathlib import Path
from shutil import rmtree
from importlib import import_module

from task_runner import run, REPO_ROOT

from ._macros import macros, zxpy  # noqa: F401 # pyright: ignore[reportAttributeAccessIssue]

import typer


def _get_prompt():
    from uoft.core import Util
    from uoft.core.prompt import Prompt

    return Prompt(Util("uoft-tools").history_cache)


def exec(cmd: str):
    "Execute a python function in the virtualenv (ex: --exec uoft.aruba.cli:_debug to execute the _debug function in the uoft.aruba.cli module)"
    module_name, func_name = cmd.split(":")
    module = import_module(module_name)
    func = getattr(module, func_name)
    func()
    raise typer.Exit(0)


def list_projects():
    """list all projects"""
    from tasks import all_projects_by_name
    return all_projects_by_name()


@no_type_check
def build(project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project}")
    run(f"pants package src/{project}")


@no_type_check
def build_all(clean_first: bool = False):
    """build sdist and wheel packages for all projects"""
    if clean_first:
        clean()

    run("pants package ::")

def clean():
    """clean dist/ directory"""
    # delete everything in dist/ except for `export`
    dist = REPO_ROOT / "dist"
    for item in dist.iterdir():
        if item.name != "export":
            if item.is_dir():
                rmtree(item)
            else:
                item.unlink()

def test(project: str):
    """run tests for a given project"""
    print(f"testing {project} from projects/{project}")
    run(f"python -m pytest -k {project}")


def test_all():
    """run tests for all projects"""
    run("python -m pytest --integration --end-to-end")


def test_inline(cmd: str):
    """
    run tests with an in-process pytest invocation,
    useful when combined with --debug
    """
    from pytest import main as pytest_main

    pytest_args = cmd.split(" ")
    pytest_main(pytest_args)


def coverage():
    """run coverage on all projects"""
    run("pytest --cov-config=.coveragerc --cov-report xml:cov.xml --cov")


def new_project(name: str):
    """create a new project from the copier template at tasks/_new_project/template"""
    # our copier template makes use of a jinja extension in a module inside tasks/_new_project
    # we need to add that module to the python path so that copier can find it
    os.environ["PYTHONPATH"] = str(REPO_ROOT / "tasks/_new_project")
    # copier does not like being run inside of an invoke task runner,
    # so we shell out to the system to call it instead
    return_code = os.system(
        f"copier copy --trust -d name={name} tasks/_new_project/template {REPO_ROOT}/src/uoft/{name}"
    )
    if not return_code == 0:
        raise Exception("copier failed")

    # tell pants about the new dist to beuild an editable install for it
    run("pants generate-lockfiles")
    run("pants export --resolve=python-default")


def repl(project: Annotated[Optional[str], typer.Argument()] = None):
    """start a python repl with a given project imported"""
    if not project:
        project = "core"

    assert (REPO_ROOT / f"src/uoft/{project}").exists(), f"Project {project} does not exist"

    print(f"starting repl with uoft/.{project} imported")
    with TemporaryDirectory() as tmpdir:
        prelude = Path(tmpdir) / "prelude.py"
        prelude.write_text(
            dedent(
                f"""\
                    import sys
                    import os
                    import json
                    from pathlib import Path
                    from uoft.core import shell, txt, lst, chomptxt
                    from uoft.core.prompt import Prompt
                    from rich.pretty import pprint
                    import uoft.{project}
                    print("The following modules/functions are imported and available:")
                    print("os, sys, json, Path, shell, txt, lst, chomptxt, Prompt, pprint, uoft.{project}")
                    try:
                        from uoft.{project}.conf import Settings
                        print("`Settings` from uoft.{project}.conf is also imported")
                    except ImportError:
                        pass
                """
            )
        )
        os.system(f"ptipython -i {prelude}")


def global_install(package: str):
    """install a package (ie uoft.aruba) to /usr/local/bin through pipx"""
    from tasks import pipx_install
    pipx_install(package)


def global_install_all():
    """install all packages to /usr/local/bin through pipx"""
    from tasks import all_projects_by_name_except_core, pipx_install
    projects = all_projects_by_name_except_core()
    pipx_install("uoft.core", list(projects))


def package_inspect():
    """list the contents of an sdist or wheel file in the dist/ directory"""

    dist = REPO_ROOT / "dist"
    os.chdir(dist)
    prompt = _get_prompt()
    package = prompt.get_path("package", "Enter a filename for a package to inspect", fuzzy_search=True)
    cmd = "tar -tvf" if package.name.endswith(".tar.gz") else "unzip -l"
    run(f"{cmd} {package}", cwd=dist)


def package_peek():
    """print out the contents of a file in an sdist or wheel file in the dist/ directory"""
    prompt = _get_prompt()
    os.chdir(REPO_ROOT / "dist")
    package = prompt.get_path("package", "Enter a filename for a package to inspect", fuzzy_search=True)
    names = []
    if package.name.endswith(".tar.gz"):
        import tarfile

        with tarfile.open(package) as tar:
            names = tar.getnames()
            filename = prompt.get_from_choices(
                "filename",
                choices=names,
                description="Which file to peek at?",
                fuzzy_search=True,
            )
            embedded_file = tar.extractfile(filename)
            assert embedded_file, f"Could not find file {filename} in {package}"
            with embedded_file as f:
                print(f.read().decode("utf-8"))
    elif package.name.endswith((".whl", ".zip", ".pex")):
        import zipfile

        with zipfile.ZipFile(package) as z:
            names = z.namelist()
            filename = prompt.get_from_choices(
                "filename",
                choices=names,
                description="Which file to peek at?",
                fuzzy_search=True,
            )
            with z.open(filename) as f:
                print(f.read().decode("utf-8"))
    else:
        raise Exception(f"Unknown package type: {package}")


def profile_import_time(cmd: str):
    """Run a given command with python's `importtime` option set,
    collect the generated report, convert it to json,
    and open it in VS Code to drill-down & explore"""
    import subprocess

    res = subprocess.run(cmd, capture_output=True, shell=True, env=os.environ | {"PYTHONPROFILEIMPORTTIME": "1"})
    stderr = res.stderr.decode("utf-8")
    Path("importtime.txt").write_text(stderr)
    import sys

    try:
        subprocess.run("tuna importtime.txt", shell=True)
    except KeyboardInterrupt:
        pass
    Path("importtime.txt").unlink()


def uoft():
    """run the uoft cli"""
    from uoft.core import __main__ as cli
    import sys

    # remove all arguments before "uoft" from sys.argv
    for arg in sys.argv[:]:
        if arg == "uoft":
            break
        else:
            sys.argv.remove(arg)
    cli._add_subcommands()
    cli.app()
