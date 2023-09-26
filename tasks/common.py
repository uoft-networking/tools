"""common tasks for all projects in the repo"""
import os
from pathlib import Path
from textwrap import dedent
from tempfile import TemporaryDirectory, NamedTemporaryFile
import re

from invoke.tasks import task
from invoke.context import Context

from . import ROOT

GLOBAL_PIPX = "sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx"


def _all_projects():
    return sorted(ROOT.glob("projects/*"))


def _all_projects_by_name():
    return set([p.name for p in _all_projects()])


def _all_projects_by_name_except_core():
    return _all_projects_by_name().symmetric_difference({"core"})

def _get_prompt():
    from uoft_core import Util
    from uoft_core.prompt import Prompt
    return Prompt(Util("uoft-tools").history_cache)


def _pipx_install(c: Context, root_project: str, packages: list[str] | None = None):
    """install a package to /usr/local/bin through pipx"""
    requirements = []
    if packages:
        packages = [f"projects/{p}" for p in packages]

    with open("requirements.lock", "r") as f:
        for line in f.readlines():
            if line.startswith("-e"):
                continue
            else:
                requirements.append(line)

    with NamedTemporaryFile(mode="w", prefix="req", suffix=".txt") as req_file:
        req_file.writelines(requirements)
        req_file.flush()
        with_constraints = f'--pip-args "--constraint {req_file.name}"'
        c.run(f"{GLOBAL_PIPX} install projects/{root_project} {with_constraints}")
        if packages:
            packages_str = " ".join(packages)
            c.run(
                f"{GLOBAL_PIPX} inject --include-apps uoft_{root_project} {packages_str} {with_constraints}"
            )


def _needs_sudo(c: Context):
    """
    Called from functions which need to run sudo.
    Pulls sudo password from `pass sudo` if sudo password not already set
    """
    if not c.config.sudo.password:
        from uoft_core import shell

        try:
            c.config.sudo.password = shell("pass sudo")
        except Exception as e:
            raise Exception(
                "sudo.password config not set, and shell command `pass sudo` failed"
            ) from e


@task
def cog_files(c: Context):
    "Run cog against all cog files in the repo"
    c.run(f"cog -r -I {ROOT}/tasks/ projects/*/README.md")


@task()
def build(c: Context, project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project} from projects/{project}")
    # by default, rye builds an sdist first, and a wheel from the sdist. For some reason,
    # the pyproject.py build hook doesn't get included in the sdist, and the subsequent
    # wheel build fails. So we build the sdist and wheel separately.
    c.run(f"rye build -p uoft_{project} --sdist", pty=True)
    c.run(f"rye build -p uoft_{project} --wheel", pty=True)


@task()
def build_all(c: Context):
    """build sdist and wheel packages for all projects"""
    # by default, rye builds an sdist first, and a wheel from the sdist. For some reason,
    # the pyproject.py build hook doesn't get included in the sdist, and the subsequent
    # wheel build fails. So we build the sdist and wheel separately.
    c.run("rye build --all --clean --sdist", pty=True)
    c.run("rye build --all --wheel", pty=True)


@task()
def update_pyproject_build_hooks(c: Context):
    """update all pyproject.py build hooks"""
    for project in _all_projects_by_name():
        print(f"updating build hook for {project}")
        c.run(f"cp tasks/_new_project/template/pyproject.py projects/{project}/pyproject.py", pty=True)


@task()
def rebuild_lock_files(c: Context):
    """gather all dependencies for all projects and rebuild the lock files"""
    # rye uses pip-tools to build lock files, pip-tools uses pip to gather all dependencies
    # pip uses a vendored copy of resolvelib to resolve dependencies. resolvelib has a bug
    # when dealing with relative link dependencies. if the root project has an editable install
    # link to a project, and another project has a direct link reference to that same project,
    # resolvelib will throw a RequirementsConflicted exception, because it thinks the two
    # projects are different versions of the same project. This is a problem because rye
    # automatically and implicitly adds editable links to all projects in the repo to the root
    # project. To work around this, we need to remove the direct link references from all
    # projects before rebuilding the lock files, and then put them back afterwards
    import toml
    for project in _all_projects():
        original = project / "pyproject.toml"
        backup = original.with_suffix(".bak")
        c.run(f"cp {original} {backup}")
        d = toml.load(original)
        for dep in d['project']['dependencies'][:]:
            if dep.startswith("uoft_"):
                d['project']['dependencies'].remove(dep)
        with open(original, "w") as f:
            toml.dump(d, f)
    try:
        c.run("rye lock -v", pty=True)
    finally:
        for project in _all_projects():
            original = project / "pyproject.toml"
            backup = original.with_suffix(".bak")
            c.run(f"mv {backup} {original}")


@task()
def sync_venv(c: Context, lock: bool = False):
    """sync the virtual environment with the latest dependencies"""
    if lock:
        rebuild_lock_files(c)
    c.run("rye sync --no-lock")


@task()
def test(c: Context, project: str):
    """run tests for a given project"""

    print(f"testing {project} from projects/{project}")
    c.run(f"python -m pytest -k {project}", pty=True)


@task()
def test_all(c: Context):
    """run tests for all projects"""
    c.run("python -m pytest --integration --end-to-end", pty=True)


@task()
def coverage(c: Context):
    """run coverage on all projects"""
    c.run("pytest --cov-config=.coveragerc --cov-report xml:cov.xml --cov", pty=True)


@task()
def list_projects(c: Context):
    """list all projects"""
    print(_all_projects_by_name())


@task()
def new_project(c: Context, name: str):
    """create a new project from the copier template at tasks/_new_project/template"""
    # our copier template makes use of a jinja extension in a module inside tasks/_new_project
    # we need to add that module to the python path so that copier can find it
    os.environ["PYTHONPATH"] = str(ROOT / "tasks/_new_project")
    # copier does not like being run inside of an invoke task runner,
    # so we shell out to the system to call it instead
    return_code = os.system(
        f"copier copy --trust -d name={name} tasks/_new_project/template {ROOT}/projects/{name}"
    )
    if not return_code == 0:
        raise Exception("copier failed")
    # add the new project to the lock file and install in editable mode
    sync_venv(c, lock=True)

@task()
def repl(c: Context, project: str):
    """start a python repl with a given project imported"""

    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"

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


@task()
def changes_since_last_tag(c: Context):
    """print changes since last tag"""
    print("changes since last tag")
    c.run("git --no-pager log --oneline $(git describe --tags --abbrev=0)..HEAD")


@task()
def global_install(c: Context, package: str):
    """install a package to /usr/local/bin through pipx"""
    _pipx_install(c, f"projects/{package}")


@task()
def global_install_all(c: Context):
    """install all packages to /usr/local/bin through pipx"""
    projects = [f"projects/{p}" for p in _all_projects_by_name_except_core()]
    _pipx_install(c, "projects/core", projects)


@task()
def package_inspect(c: Context):
    """list the contents of an sdist or wheel file in the dist/ directory"""

    os.chdir(ROOT / "dist")
    prompt = _get_prompt()
    package = prompt.get_path(
        "package", "Enter a filename for a package to inspect", fuzzy_search=True
    )
    if package.name.endswith(".tar.gz"):
        c.run(f"tar -tvf {package}")
    elif package.name.endswith(".whl"):
        c.run(f"unzip -l {package}")
    else:
        raise Exception(f"Unknown package type: {package}")


@task()
def package_peek(c: Context):
    """print out the contents of a file in an sdist or wheel file in the dist/ directory"""
    prompt = _get_prompt()
    os.chdir(ROOT / "dist")
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


@task()
def debug_pydantic(c: Context, undo: bool = False):
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
