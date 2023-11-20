import re
import logging

from task_runner import run, REPO_ROOT
from task_runner import macros, coco_compile  # noqa: F401

logger = logging.getLogger(__name__)


def _my_branch():
    """get the name of the current branch"""
    return run("git rev-parse --abbrev-ref HEAD", cap=True)


def _make_git_safe():
    """prompt user to commit or stash changes if working tree is not clean"""
    res = run("git status", cap=True, check=False)
    if "nothing to commit, working tree clean" not in res:
        print("Working tree is not clean, you need to either commit or stash changes")
        stash = input("Press enter to commit changes, or type 'stash' to stash them: ")
        # if the user did anything other than press enter, `stash` will evaluate to True
        if stash:
            run("git stash")
            logger.warning("Changes stashed, don't forget to pop them later with `git stash pop`")
        else:
            run('git commit -am "."')


def _last_commit_from_my_branch_on_main():
    """get the commit hash of the last commit on the current branch that is also on main branch"""
    branch = _my_branch()
    run("git fetch origin main:main")

    # list all commits on current branch that are not on main branch, grab last one
    commit_line = run(f"git log main..{branch} --oneline", cap=True).splitlines()[-1]
    logger.info(f"Last commit on {branch} that is not on main: ")
    logger.info(commit_line)
    m = re.match(r"(\w+)", commit_line)
    assert m
    commit_hash = m.group(1)

    # get the commit hash of the parent of that commit
    parent_commit_line = run(f"git log {commit_hash}^ -n 1 --oneline", cap=True)
    logger.info(f"latest commit on {branch} that IS on main: ")
    logger.info(parent_commit_line)
    m = re.match(r"(\w+)", parent_commit_line)
    assert m
    parent_commit_hash = m.group(1)

    return parent_commit_hash


def rewrite_history():
    """rewrite history interactively for all commits on current branch that are not on main branch"""
    _make_git_safe()
    last_commit = _last_commit_from_my_branch_on_main()
    run(f"git rebase -i {last_commit}")


def last_pr():
    """get the commit hash of the last PR merged into main branch from current branch, or the given branch"""
    branch = _my_branch()
    run("git fetch origin main:main")
    cmd = f"git log main --grep='Merge pull request' --grep='{branch}' -n 1"
    res = run(cmd, cap=True)
    return re.match(r"commit (\w+)", res).group(1)

@coco_compile
def add_changes_from_main():
    """
    "use git rebase to splice in any changes from main branch into current branch"
    _make_git_safe()
    "git fetch origin main:main" |> run
    "git rebase main" |> run
    """


def latest_tag():
    """get the commit hash of the most recent git tag on the current branch"""
    tag = run("git describe --tags $(git rev-list --tags --max-count=1)", cap=True)
    print(f"The latest git tag on the current branch is {tag}")
    return tag


def files_changed_since_tag(tag: str = ""):  # type: ignore
    """List out all files that have changed since the last tag"""
    if not tag:
        tag = latest_tag()
    res = run(f"git --no-pager diff --name-only {tag} HEAD", capture_output=True).stdout  # type: ignore
    logger.info(f"There have been {len(res.splitlines())} files changed since {tag}")
    return res


def commit_msgs_since_tag(tag: str = ""):  # type: ignore
    """List out all commit messages since the last tag"""
    if not tag:
        tag = latest_tag()
    res = run(f"git --no-pager log --oneline {tag}..HEAD", capture_output=True).stdout  # type: ignore
    logger.info(f"There have been {len(res.splitlines())} commits since {tag}")
    return res


# TODO: clean up these tasks

def version():
    """get current version of repository from git tag"""
    from setuptools_scm import get_version

    version = get_version(root=str(REPO_ROOT), version_scheme="post-release")
    print(f"Current version: {version}")
    return version


def version_next(patch: bool = False):
    """
    suggest the next version to use as a git tag.
    By default, the minor version is incremented.
    Use --patch to increment the patch version instead.
    """
    from packaging.version import Version

    v = version()
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


def tag(version: str = "", push=False):  # type: ignore
    """create a new git tag with the given version, or the next version if not specified"""
    if not version:
        version = version_next()
    run(f"git tag --sign --message 'Version {version}' {version}")
    if push:
        run("git push --tags")


def should_bump_version():
    """ "
    Check if the version should be bumped based on changes since the last tag.
    """
    files = files_changed_since_tag()
    if re.search(r"projects/\w+/(uoft_|pyproject.toml)", files):
        print("Version bump required")
        return True
    print("No version bump required")
    return False


def changes_since_last_tag():
    """print changes since last tag"""
    print("changes since last tag")
    run("git --no-pager log --oneline $(git describe --tags --abbrev=0)..HEAD")
