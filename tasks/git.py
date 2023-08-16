import os
import re
from invoke.tasks import task
from invoke.context import Context
from invoke.runners import Result


@task()
def merge_from_main(c: Context):
    """pull changes to main branch and merge into current branch"""
    my_branch = os.environ.get("MY_BRANCH", input("Enter branch name: "))
    res: Result = c.run("git status", hide="stdout")  # type: ignore # c.run only returns None if paramenter disown=True
    if "nothing to commit, working tree clean" not in res.stdout:
        raise Exception("Working tree is not clean, please commit or stash changes")
    c.run("git checkout main")
    c.run("git pull")
    c.run(f"git checkout {my_branch}")
    c.run("git merge main")

@task()
def latest_tag(c: Context):
    """find and print the most recent tag on the current branch"""
    res: Result = c.run("git describe --tags --abbrev=0", hide="stdout")  # type: ignore
    if c.config.run.dry:
        return ""
    tag = res.stdout.splitlines()[0]
    print(f"The latest git tag on the current branch is {tag}")
    return tag


@task()
def version(c: Context):
    """get current version of repository from git tag"""
    from setuptools_scm import get_version
    version = get_version(root='.', version_scheme="post-release")
    print(f"Current version: {version}")
    return version


@task()
def version_next(c: Context, patch: bool = False):
    """
    suggest the next version to use as a git tag.
    By default, the mnor version is incremented.
    Use --patch to increment the patch version instead.
    """
    from packaging.version import Version

    v = version(c)
    segments = list(Version(v)._version.release)  # pylint: disable=protected-access
    if len(segments) == 2:
        segments.append(0)
    # at this point, segments should be [major, minor, patch]
    if patch:
        segments[2] += 1
    else:
        segments[1] += 1
        segments[2] = 0
    new_version = ".".join(map(str, segments))
    print(f"New version: {new_version}")
    return new_version

@task()
def tag(c: Context, version: str = '', push = False): # type: ignore
    """create a new git tag with the given version, or the next version if not specified"""
    if not version:
        version = version_next(c)
    c.run(f"git tag --sign --message 'Version {version}' {version}")
    if push:
        c.run("git push --tags")

@task()
def files_changed_since_tag(c: Context, tag: str = ''): # type: ignore
    """List out all files that have changed since the last tag"""
    if not tag:
        tag = latest_tag(c)
    res: Result = c.run(f"git --no-pager diff --name-only {tag} HEAD", hide="stdout")  # type: ignore
    print(f"Files changed since {tag}:\n{res.stdout}")
    return res.stdout

@task()
def commit_msgs_since_tag(c: Context, tag: str = ''): # type: ignore
    """List out all commit messages since the last tag"""
    if not tag:
        tag = latest_tag(c)
    res: Result = c.run(f"git --no-pager log --oneline {tag}..HEAD", hide="stdout")  # type: ignore
    print(f"Commit messages since {tag}:\n{res.stdout}")
    return res.stdout

@task()
def should_bump_version(c: Context):
    """"
    Check if the version should be bumped based on changes since the last tag.
    """
    files = files_changed_since_tag(c)
    if re.search(r"projects/\w+/(uoft_|pyproject.toml)", files):
        print("Version bump required")
        return True
    print("No version bump required")
    return False

