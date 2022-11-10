"""common tasks for all projects in the repo"""
import os

from invoke import task, Context

from . import ROOT

from setuptools_scm import get_version


def all_projects():
    return sorted(ROOT.glob("projects/*"))


def needs_sudo(c: Context):
    "called from functions which need to run sudo. pulls sudo password from `pass sudo` if sudo password not already set"
    if not c.config.sudo.password:
        from uoft_core import shell

        try:
            c.config.sudo.password = shell("pass sudo")
        except Exception as e:
            raise Exception(
                "sudo.password config not set, and shell command `pass sudo` failed"
            ) from e


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
    c.run("pytest --cov-report xml:cov.xml --cov-report term-missing --cov")


@task()
def list_projects(c: Context):
    """list all projects"""
    for p in all_projects():
        print(p.name)


@task()
def new_project(c: Context, name: str):
    c.run(f"copier -d name={name} copy tasks/new_project_template {ROOT}/projects/{name}")


@task()
def update_venv(c: Context):
    """update the virtual environment with the latest dependencies"""
    c.run("python -m pip install -r dev.requirements.txt")
    install_editable_all(c)


@task()
def install_editable(c: Context, project: str):
    """install a project in editable mode"""
    from . import ROOT

    print(f"installing projects/{project} in editable mode")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    c.run(f"python -m pip install -e projects/{project}")


@task()
def install_editable_all(c: Context):
    """install all projects in editable mode"""
    core_first = lambda p: 0 if p.name == "core" else 1
    for p in sorted(all_projects(), key=core_first):
        install_editable(c, p.name)


@task()
def changes_since_last_tag(c: Context):
    """print changes since last tag"""
    print("changes since last tag")
    c.run("git --no-pager log --oneline $(git describe --tags --abbrev=0)..HEAD")


@task()
def version(c: Context):
    """get current version of repository from git tag"""
    print(get_version(root=str(ROOT), version_scheme="post-release"))


@task()
def version_next(c: Context, minor: bool = False):
    """suggest the next version to use as a git tag"""
    from packaging.version import Version

    v = get_version(root=str(ROOT), version_scheme="post-release")
    print(f"current version: {v}")
    segments = list(Version(v)._version.release)  # pylint: disable=protected-access
    if len(segments) == 2:
        segments.append(0)
    # at this point, segments should be [major, minor, patch]
    if minor:
        segments[1] += 1
        segments[2] = 0
    else:
        segments[2] += 1
    new_version = Version(".".join(map(str, segments)))
    print(
        f"suggested command: \n\ngit tag --sign --message 'Version {new_version}' {new_version}\ngit push --tags\n"
    )


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
