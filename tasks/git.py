import os
import re
from invoke import task, Context

from tasks.common import needs_sudo

@task()
def merge_from_main(c: Context):
    """pull changes to main branch and merge into current branch"""
    my_branch = os.environ.get("MY_BRANCH", input("Enter branch name: "))
    # TODO: check and make sure 
    c.run("git checkout main")
    c.run("git pull")
    c.run(f"git checkout {my_branch}")
    c.run("git merge main")
