"""common tasks for all projects in the repo"""
from invoke import task, Context

from . import ROOT

from setuptools_scm import get_version

@task
def needs_sudo(c: Context):
    "called from functions which need to run sudo. pulls sudo password from `pass sudo` if sudo password not already set"
    if not c.config.sudo.password:
        from uoft_core import shell
        try:
            c.config.sudo.password = shell('pass sudo')
        except Exception as e:
            raise Exception('sudo.password config not set, and shell command `pass sudo` failed') from e


@task()
def build(c: Context, project: str, verbose: bool = False):
    """build sdist and wheel packages for a given project"""
    from . import ROOT
    print(f"building projects/{project}")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    r = c.run(f"python -m build -o dist/ projects/{project}")
    if verbose:
        r = r.stdout
        _, _, r = r.partition('Successfully built ')
        sdist, _, wheel = r.partition(' and ')
        c.run(f"tar -tvf dist/{sdist}")
        c.run(f"unzip -l dist/{wheel}")

@task()
def coverage(c: Context):
    """run coverage on all projects"""
    c.run("pytest --cov-report xml:cov.xml --cov-report term-missing --cov")

def all_projects():
    return sorted(ROOT.glob('projects/*'))

@task(name='list')
def list_(c: Context):
    """list all projects"""
    for p in all_projects():
        print(p.relative_to(ROOT))

@task()
def install_editable(c: Context, project: str):
    """install a project in editable mode"""
    from . import ROOT
    print(f"installing projects/{project} in editable mode")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    c.run(f"python -m pip install -e projects/{project}")

@task()
def install_all_editable(c: Context):
    """install all projects in editable mode"""
    for p in all_projects():
        install_editable(c, p.name)

@task()
def version(c: Context):
    """get current version of repository from git tag"""
    print(get_version(root=str(ROOT)))

@task()
def write_version(c: Context):
    """write current version of repository to project metadata"""
    version = get_version(root=str(ROOT))
    for p in all_projects():
        found_version = False
        with (p / 'pyproject.toml').open('r') as f:
            lines = f.readlines()
        with (p / 'pyproject.toml').open('w') as f:
            for line in lines:
                if line.startswith('version ='):
                    line = f'version = "{version}"\n'
                    found_version = True
                f.write(line)
        if not found_version:
            print(f"WARNING: no version found in {p}/pyproject.toml")
        else:
            print(f"updated {p / 'pyproject.toml'}")

@task()
def next_version(c: Context, minor: bool = False ):
    """suggest the next 
    
    version to use as a git tag
    """
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