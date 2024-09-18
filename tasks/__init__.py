from tempfile import NamedTemporaryFile

from task_runner import run, sudo, REPO_ROOT

GLOBAL_PIPX = "PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx"


def pipx_raw(command: str):
    with NamedTemporaryFile(mode="w", prefix="req", suffix=".txt") as req_file:
        run(f"uv export --no-hashes --no-emit-workspace --output-file {req_file.name}", cap=True)
        print(f"Using constraints file: {req_file.name}")
        with_pipargs = f'--pip-args "--constraint {req_file.name} --config-settings dependencies=local"'
        sudo(
            f"{GLOBAL_PIPX} {command} {with_pipargs}",
        )


def pipx_install(root_project: str, packages: list[str] | None = None):
    """install a package to /usr/local/bin through pipx"""
    pipx_raw(f"install --force projects/{root_project}")

    if packages:
        packages = [f"projects/{p}" for p in packages]
        packages_str = " ".join(packages)
        pipx_raw(
            f"inject --include-apps uoft_{root_project} {packages_str}",
        )


def all_projects():
    return sorted(REPO_ROOT.glob("projects/*"))


def all_projects_by_name():
    return set([p.name for p in all_projects()])


def all_projects_by_name_except_core():
    return all_projects_by_name().symmetric_difference({"core"})
