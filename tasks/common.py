"""common tasks for all projects in the repo"""
import os
from pathlib import Path

from invoke import task, Context

from . import ROOT


def all_projects():
    return sorted(ROOT.glob("projects/*"))

def all_projects_by_name():
    return set([p.name for p in all_projects()])

def all_projects_by_name_except_core():
    return all_projects_by_name().symmetric_difference({"core"})


def needs_sudo(c: Context):
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
    c.run("cog -r -I . projects/*/README.md")


@task()
def build(c: Context, project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project} from projects/{project}")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    c.run(f"python -m build --sdist --outdir {ROOT}/dist/ projects/{project}")
    c.run(f"python -m build --wheel --outdir {ROOT}/dist/ projects/{project}")


@task()
def build_all(c: Context):
    """build sdist and wheel packages for all projects"""
    c.run("rm dist/*")
    for project in all_projects():
        build(c, project.name)


@task()
def test(c: Context, project: str):
    """run tests for a given project"""
    from . import ROOT

    print(f"testing {project} from projects/{project}")
    assert (ROOT / f"tests/{project}").exists(), f"No tests found for project {project}"
    c.run(f"python -m pytest tests/{project}")


@task()
def test_all(c: Context):
    """run tests for all projects"""
    for p in all_projects():
        test(c, p.name)


@task()
def coverage(c: Context):
    """run coverage on all projects"""
    c.run("pytest --cov-config=.coveragerc --cov-report xml:cov.xml --cov")


@task()
def list_projects(c: Context):
    """list all projects"""
    print(all_projects_by_name())


@task()
def new_project(c: Context, name: str):
    """create a new project from the copier template at tasks/new_project_template"""
    # copier does not include the current directory in python path, so we need to add it
    # this is needed so that copier can import jinja extensions from the tasks directory
    os.environ["PYTHONPATH"] = str(ROOT)
    # copier does not like being run inside of an invoke task runner,
    # so we shell out to the system to call it instead
    os.system(
        # --UNSAFE is needed so we can run our custom template extensions
        f"copier copy -d name={name} --UNSAFE tasks/new_project_template {ROOT}/projects/{name}"
    )
    install_editable(c, name)


@task()
def update_venv(c: Context):
    """update the virtual environment with the latest dependencies"""
    c.run("python -m pip install -r dev.requirements.txt")
    install_editable_all(c)


@task()
def install_editable(c: Context, project: str, include_core: bool = True):
    """install a project in editable mode"""
    from . import ROOT

    if project != "core":
        print("bumping uoft_core editable install version number...")
        install_editable(c, "core")

    print(f"installing projects/{project} in editable mode")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    c.run(f"python -m pip install -e projects/{project}")


@task()
def install_editable_all(c: Context):
    """install all projects in editable mode"""
    install_editable(c, "core")
    for p in all_projects_by_name_except_core():
        install_editable(c, p, include_core=False)


@task()
def repl(c: Context, project: str):
    """start a python repl with a given project imported"""
    from . import ROOT
    from textwrap import dedent
    from pathlib import Path
    from tempfile import TemporaryDirectory

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
def global_deploy_pipx(c: Context, path: str):
    """deploy all projects to /usr/local/bin via pipx"""
    needs_sudo(c)
    c.sudo("PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install --force projects/core")
    c.sudo(f"PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx inject --force uoft_core {path}")


@task()
def package_inspect(c: Context):
    """list the contents of an sdist or wheel file in the dist/ directory"""
    from . import ROOT
    from uoft_core import Util
    from uoft_core.prompt import Prompt

    prompt = Prompt(Util("uoft-tools").history_cache)
    os.chdir(ROOT / "dist")
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
    from . import ROOT
    from uoft_core import Util
    from uoft_core.prompt import Prompt

    prompt = Prompt(Util("uoft-tools").history_cache)
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
        for ext in Path('.venv').glob('lib/python*/site-packages/pydantic/*.cpython-*.so.disabled'):
            print(f"renaming {ext.name} to {ext.with_suffix('').name}")
            ext.rename(ext.with_suffix(''))
    else:
        for ext in Path('.venv').glob('lib/python*/site-packages/pydantic/*.so'):
            print(f"renaming {ext.name} to {ext.with_suffix('.so.disabled').name}")
            ext.rename(ext.with_suffix('.so.disabled'))

    
