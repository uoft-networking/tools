from tempfile import NamedTemporaryFile
from pathlib import Path

from task_runner import run, sudo, REPO_ROOT

import mcpyrate.activate # activate the macro system before importing any task modules that us it # noqa: F401

GLOBAL_PIPX = "PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx"


def pipx_raw(command: str):
    with NamedTemporaryFile(mode="w", prefix="req", suffix=".txt") as req_file:
        run(f"uv export --no-hashes --no-emit-workspace --output-file {req_file.name}", cap=True)
        print(f"Using constraints file: {req_file.name}")
        with_pipargs = f'--pip-args "--force --find-links dist/ --constraint {req_file.name}"'
        sudo(
            f"{GLOBAL_PIPX} {command} {with_pipargs}",
        )


def pipx_install(root_project: str|Path, packages: list[str|Path] | None = None, extra_args: str = "", root_project_name: str | None = None):
    """install a package (ie uoft.scripts of uoft_nautobot) to /usr/local/bin through pipx"""
    run("pants package :: --filter-target-type=python_distribution") # if package is already built, this is a no-op
    pipx_raw(f"install --force {extra_args} {root_project}")

    if packages:
        packages_str = " ".join([str(p) for p in packages])
        pipx_raw(
            f"inject --include-apps {root_project_name or root_project} {packages_str}",
        )


def all_projects():
    res: list[Path] = []
    # add all top-level folders in src except `uoft` and `apps`
    for folder in REPO_ROOT.glob("src/*"):
        if folder.is_dir() and folder.name not in {"uoft", "apps"}:
            res.append(folder)

    for folder in (REPO_ROOT / "src/uoft").iterdir():
        if folder.is_dir():
            res.append(folder)
    return sorted(res, key=lambda p: p.name)


def all_projects_by_name():
    return list(set([str(p.relative_to(REPO_ROOT / "src")).replace("/", ".") for p in all_projects()]))


def all_projects_by_name_except_core():
    res = all_projects_by_name()
    res.remove("uoft.core")
    return res
