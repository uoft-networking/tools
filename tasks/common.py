"""common tasks for all projects in the repo"""
from invoke import task, Context

from . import ROOT

@task()
def build(ctx: Context, project: str, verbose: bool = False):
    """build sdist and wheel packages for a given project"""
    print(f"building projects/{project}")
    assert (ROOT / f"projects/{project}").exists(), f"Project {project} does not exist"
    r = ctx.run(f"python -m build -o dist/ projects/{project}")
    if verbose:
        r = r.stdout
        _, _, r = r.partition('Successfully built ')
        sdist, _, wheel = r.partition(' and ')
        ctx.run(f"tar -tvf dist/{sdist}")
        ctx.run(f"unzip -l dist/{wheel}")

@task()
def coverage(ctx: Context):
    ctx.run("pytest --cov-report xml:cov.xml --cov-report term-missing --cov")