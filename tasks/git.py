import os
import re
from invoke import task, Context, Result

from tasks.common import needs_sudo

@task()
def merge_from_main(c: Context):
    """pull changes to main branch and merge into current branch"""
    my_branch = os.environ.get("MY_BRANCH", input("Enter branch name: "))
    res: Result = c.run("git status")
    if "nothing to commit, working tree clean" not in res.stdout:
        raise Exception("Working tree is not clean, please commit or stash changes")
    c.run("git checkout main")
    c.run("git pull")
    c.run(f"git checkout {my_branch}")
    c.run("git merge main")
