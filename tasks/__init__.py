import os
from pathlib import Path

# all tasks should run relative to the project root,
# so we will set the working directory to the project root at the moment invoke imports tasks
# when running subtasks with invoke called from a parent invoke task, 
# we want the subtask to run in whichever directory we told it to
ROOT = Path(__file__).parent.parent
CWD = os.getcwd()
if not os.environ.get("RUNNING_INSIDE_INVOKE"):
    os.chdir(ROOT)
    os.environ["RUNNING_INSIDE_INVOKE"] = 'true'


# Invoke currently still supports python 2.7, and therefore does not support annotations in task signatures
# This is a workaround to make it work until Invoke finally drops support for python 2.7
from unittest.mock import patch
from inspect import getfullargspec, ArgSpec
import invoke

def fix_annotations():
    """
        Pyinvoke doesnt accept annotations by default, this fix that
        Based on: https://github.com/pyinvoke/invoke/pull/606
    """
    def patched_inspect_getargspec(func):
        spec = getfullargspec(func)
        return ArgSpec(*spec[0:4]) # type: ignore

    org_task_argspec = invoke.tasks.Task.argspec

    def patched_task_argspec(*args, **kwargs):
        with patch(target="inspect.getargspec", new=patched_inspect_getargspec):
            return org_task_argspec(*args, **kwargs)

    invoke.tasks.Task.argspec = patched_task_argspec

fix_annotations()


# import tasks
from invoke import Collection
from . import common, nautobot

ns = Collection.from_module(common)
ns.add_collection(nautobot)