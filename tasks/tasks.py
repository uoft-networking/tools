"""top-level tasks for the monorepo"""
import os

from . import pipx_install
from task_runner import macros, lazy_imports, coco_compile  # noqa: F401
from task_runner import run, REPO_ROOT

with lazy_imports:  # type: ignore
    from pathlib import Path
    from textwrap import dedent
    from tempfile import TemporaryDirectory


def _all_projects():
    return sorted(REPO_ROOT.glob("projects/*"))


def _all_projects_by_name():
    return set([p.name for p in _all_projects()])


def _all_projects_by_name_except_core():
    return _all_projects_by_name().symmetric_difference({"core"})

def _get_prompt():
    from uoft_core import Util
    from uoft_core.prompt import Prompt
    return Prompt(Util("uoft-tools").history_cache)


def cog_files():
    "Run cog against all cog files in the repo"
    run(f"cog -r -I {REPO_ROOT}/tasks/ projects/*/README.md projects/core/uoft_core/__main__.py")


@coco_compile
def example_coconut_fn(arg: str):
    """
    "example docstring" # This will end up being the docstring / help text for this function / task
    'hello world' |> print  # supports coconut syntax like pipes
    arg + REPO_ROOT |> print # the function body has full access to args and globals
    """


def lock():
    import tomlkit
    reqs = []
    dev_reqs = []
    for p in Path(REPO_ROOT).glob("projects/*/pyproject.toml"):
        pyproj = tomlkit.load(p.open())
        reqs.extend(pyproj.get('project', {}).get("dependencies", []))
    root_pyproj = tomlkit.load((REPO_ROOT / "pyproject.toml").open())
    dev_reqs.extend(root_pyproj.get('tool', {}).get('rye', {}).get("dev-dependencies", []))

    import tempfile
    with tempfile.NamedTemporaryFile() as f:
        f.write("\n".join(reqs).encode("utf-8"))
        f.flush()
        run(f"pipgrip --tree -r {f.name}")


def build(project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project} from projects/{project}")
    # by default, rye builds an sdist first, and a wheel from the sdist. For some reason,
    # the pyproject.py build hook doesn't get included in the sdist, and the subsequent
    # wheel build fails. So we build the sdist and wheel separately.
    run(f"rye build -p uoft_{project} --sdist")
    run(f"rye build -p uoft_{project} --wheel")



def build_all():
    """build sdist and wheel packages for all projects"""
    # by default, rye builds an sdist first, and a wheel from the sdist. For some reason,
    # the pyproject.py build hook doesn't get included in the sdist, and the subsequent
    # wheel build fails. So we build the sdist and wheel separately.
    run("rye build --all --clean --sdist")
    run("rye build --all --wheel")



def update_pyproject_build_hooks():
    """update all pyproject.py build hooks"""
    for project in _all_projects_by_name():
        print(f"updating build hook for {project}")
        run(f"cp tasks/_new_project/template/pyproject.py projects/{project}/pyproject.py")



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



def list_projects():
    """list all projects"""
    print(_all_projects_by_name())



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
    run("rye sync")


def repl(project: str):
    """start a python repl with a given project imported"""

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



def changes_since_last_tag():
    """print changes since last tag"""
    print("changes since last tag")
    run("git --no-pager log --oneline $(git describe --tags --abbrev=0)..HEAD")


def global_install(package: str):
    """install a package to /usr/local/bin through pipx"""
    pipx_install(package)



def global_install_all():
    """install all packages to /usr/local/bin through pipx"""
    projects = _all_projects_by_name_except_core()
    pipx_install("core", list(projects))


def package_inspect():
    """list the contents of an sdist or wheel file in the dist/ directory"""

    os.chdir(REPO_ROOT / "dist")
    prompt = _get_prompt()
    package = prompt.get_path(
        "package", "Enter a filename for a package to inspect", fuzzy_search=True
    )
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
    package = prompt.get_path(
        "package", "Enter a filename for a package to inspect", fuzzy_search=True
    )
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
