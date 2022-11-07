"""common tasks for all projects in the repo"""
from invoke import task, Context

from . import ROOT

from setuptools_scm import get_version

def all_projects():
    return sorted(ROOT.glob('projects/*'))


def needs_sudo(c: Context):
    "called from functions which need to run sudo. pulls sudo password from `pass sudo` if sudo password not already set"
    if not c.config.sudo.password:
        from uoft_core import shell
        try:
            c.config.sudo.password = shell('pass sudo')
        except Exception as e:
            raise Exception('sudo.password config not set, and shell command `pass sudo` failed') from e


@task()
def build(c: Context, project: str):
    """build sdist and wheel packages for a given project"""
    print(f"building {project} from projects/{project}")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    r = c.run(f"python -m build -o {ROOT}/dist/ projects/{project}")

@task()
def build_all(c: Context):
    """build sdist and wheel packages for all projects"""
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
def install_editable(c: Context, project: str):
    """install a project in editable mode"""
    from . import ROOT
    print(f"installing projects/{project} in editable mode")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    c.run(f"python -m pip install -e projects/{project}")

@task()
def install_editable_all(c: Context):
    """install all projects in editable mode"""
    for p in all_projects():
        install_editable(c, p.name)
        
@task()
def changes_since_last_tag(c: Context):
    """print changes since last tag"""
    print(f"changes since last tag")
    c.run(f"git --no-pager log --oneline $(git describe --tags --abbrev=0)..HEAD")

@task()
def version(c: Context):
    """get current version of repository from git tag"""
    print(get_version(root=str(ROOT)))

@task()
def version_write(c: Context):
    """write current version of repository to project metadata"""
    from tomlkit import parse, dumps, items

    def update_core_dep(deps: list, v: str):
        for d in deps:
            if 'uoft_core' in d:yield 'uoft_core == ' + v
            else:yield d

    version = get_version(root=str(ROOT))
    for p in all_projects():
        meta = parse((p / 'pyproject.toml').read_text())
        project_meta: items.Table = meta['project']  # type: ignore
        project_meta['version'] = version
        deps: items.Array = project_meta['dependencies']  # type: ignore

        for i, dep in enumerate(deps):
            if 'uoft_core' in dep:
                deps[i] = 'uoft_core == ' + version
                break

        (p / 'pyproject.toml').write_text(dumps(meta))
        print(f"updated {p / 'pyproject.toml'}")

@task()
def version_next(c: Context, minor: bool = False ):
    """suggest the next version to use as a git tag"""
    from packaging.version import Version
    v = get_version(root=str(ROOT))
    print(f"current version: {v}")
    current_version = v.split('+')[0]
    segments = list(Version(v)._version.release)
    if len(segments) == 2:
        segments.append(0)
    # at this point, segments should be [major, minor, patch]
    if minor:
        segments[1] += 1
        segments[2] = 0
    else:
        segments[2] += 1
    new_version = Version('.'.join(map(str, segments)))
    print(f"suggested command: \n\ngit tag --sign --message 'Version {new_version}' {new_version}\ngit push --tags\n")