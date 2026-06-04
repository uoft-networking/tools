from pathlib import Path
from tempfile import NamedTemporaryFile

from task_runner import run, REPO_ROOT


from ._macros import macros, zxpy  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType] # noqa: F401


def cog_update():
    """
    Update the cog file registry,
    the registry of all files in the repo which cog should be run against
    """
    from shutil import which

    rg_path = ""
    if rg := which("ripgrep"):
        rg_path = rg
    elif rg := which("ripgrep.rg"):
        rg_path = rg
    else:
        print("Aquiring ripgrep...")
        run("pants export --bin=ripgrep")
        rg_path = REPO_ROOT / "dist/export/bin/ripgrep"
    res = run(f"{rg_path} --glob !tasks/* --files-with-matches --fixed-strings '[[[cog' {REPO_ROOT}", cap=True)

    # ripgrep sometimes returns files in different order.
    # We sort the list here to minimize churn in the
    # .cog-files registry
    res = "\n".join(sorted(res.strip().splitlines()))
    Path(".cog-files").write_text(res.strip())


def cog_run(target_dir: str | None = None):
    "Run cog against all cog files in a directory or the whole repo"

    def _run_cog(file: str):
        from cogapp import Cog

        # -r = inplace edit (replace the input file with the output)
        # -p = prologue, prepend this line to the top of each cog block before executing it
        Cog().callable_main(["cog", "-r", "-pimport tasks._coghelpers", f"@{file}"])

    target_files = Path(".cog-files")
    if not target_files.exists():
        print("cog file registry not found, updating...")
        cog_update()

    if target_dir:
        target_files = [f for f in target_files.read_text().splitlines() if target_dir in f]
        with NamedTemporaryFile("w+") as tf:
            tf.write("\n".join(target_files))
            tf.seek(0)
            _run_cog(tf.name)
    else:
        _run_cog(".cog-files")


def debug_pydantic(undo: bool = False):
    """disable pydantic compiled modules in virtualenv so we can step through the python code"""
    if undo:
        for ext in Path(".venv").glob("lib/python*/site-packages/pydantic/*.cpython-*.so.disabled"):
            print(f"renaming {ext.name} to {ext.with_suffix('').name}")
            ext.rename(ext.with_suffix(""))
    else:
        for ext in Path(".venv").glob("lib/python*/site-packages/pydantic/*.so"):
            print(f"renaming {ext.name} to {ext.with_suffix('.so.disabled').name}")
            ext.rename(ext.with_suffix(".so.disabled"))


def lock():
    """update the monorepo lock file"""
    run("pants generate-lockfiles --resolve=python-default")
