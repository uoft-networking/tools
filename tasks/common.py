"""common tasks for all projects in the repo"""
from invoke import task, Context

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
    c.run("pytest --cov-report xml:cov.xml --cov-report term-missing --cov")