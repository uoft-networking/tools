"""top-level tasks for the monorepo"""

import os
from typing import Annotated, Optional, no_type_check
from textwrap import dedent
from tempfile import TemporaryDirectory
from pathlib import Path
from shutil import rmtree

from . import pipx_install, all_projects_by_name, all_projects_by_name_except_core
from task_runner import run, REPO_ROOT

from ._macros import macros, zxpy  # noqa: F401 # type: ignore

import typer


def _get_prompt():
    from uoft_core import Util
    from uoft_core.prompt import Prompt

    return Prompt(Util("uoft-tools").history_cache)


def list_projects():
    """list all projects"""
    return all_projects_by_name()


@no_type_check
def build(project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project} from projects/{project}")
    run(f"uv build --package uoft_{project} --out-dir {REPO_ROOT}/dist")
    rmtree(REPO_ROOT / "projects" / project / ".pdm-build")


@no_type_check
def build_all(clean: bool = False):
    """build sdist and wheel packages for all projects"""
    if clean:
        rmtree(REPO_ROOT / "dist")
    for project in all_projects_by_name():
        build(project)


def test(project: str):
    """run tests for a given project"""
    print(f"testing {project} from projects/{project}")
    run(f"python -m pytest -k {project}")


def test_all():
    """run tests for all projects"""
    run("python -m pytest --integration --end-to-end")


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
        f"copier copy --trust -d name={name} tasks/_new_project/template {REPO_ROOT}/projects/{name}"
    )
    if not return_code == 0:
        raise Exception("copier failed")
    # add the new project to the lock file and install in editable mode
    from .repo import lock
    lock()
    run("uv sync --frozen")


def repl(project: Annotated[Optional[str], typer.Argument()] = None):
    """start a python repl with a given project imported"""
    if not project:
        project = "core"

    assert (REPO_ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"

    print(f"starting repl with uoft_{project} imported")
    with TemporaryDirectory() as tmpdir:
        prelude = Path(tmpdir) / "prelude.py"
        prelude.write_text(
            dedent(
                f"""\
                    import sys
                    import os
                    from pathlib import Path
                    from uoft_core import shell, txt, lst, chomptxt
                    from uoft_core.prompt import Prompt
                    import uoft_{project}
                    if hasattr(uoft_{project}, "Settings"):
                        Settings = uoft_{project}.Settings
                    print("The following modules/functions are imported and available:")
                    print("os, sys, Path, shell, txt, lst, chomptxt, Prompt, uoft_{project}, Settings")
                """
            )
        )
        os.system(f"ptipython -i {prelude}")


def global_install(package: str):
    """install a package to /usr/local/bin through pipx"""
    pipx_install(package)


def global_install_all():
    """install all packages to /usr/local/bin through pipx"""
    projects = all_projects_by_name_except_core()
    pipx_install("core", list(projects))


def package_inspect():
    """list the contents of an sdist or wheel file in the dist/ directory"""

    os.chdir(REPO_ROOT / "dist")
    prompt = _get_prompt()
    package = prompt.get_path("package", "Enter a filename for a package to inspect", fuzzy_search=True)
    if package.name.endswith(".tar.gz"):
        run(f"tar -tvf {package}")
    elif package.name.endswith(".whl"):
        run(f"unzip -l {package}")
    else:
        raise Exception(f"Unknown package type: {package}")


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
    import tempfile
    from shutil import which

    print(which('uoft'))

    res = subprocess.run(cmd, capture_output=True, shell=True, env={"PYTHONPROFILEIMPORTTIME": "1"})
    stderr = res.stderr.decode("utf-8")
    Path("importtime.txt").write_text(stderr)
    import sys
    print(sys.executable)
    try:
        subprocess.run('tuna importtime.txt', shell=True)
    except KeyboardInterrupt:
        pass
    Path("importtime.txt").unlink()


def uoft():
    """run the uoft cli"""
    from uoft_core import __main__ as cli
    import sys

    # remove all arguments before "uoft" from sys.argv
    for arg in sys.argv[:]:
        if arg == "uoft":
            break
        else:
            sys.argv.remove(arg)
    cli._add_subcommands()
    cli.app()
