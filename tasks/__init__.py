from tempfile import NamedTemporaryFile

from task_runner import run, sudo, REPO_ROOT

GLOBAL_PIPX = "PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx"


def pipx_install(root_project: str, packages: list[str] | None = None):
    """install a package to /usr/local/bin through pipx"""
    requirements = []
    if packages:
        packages = [f"projects/{p}" for p in packages]

    with open("requirements.lock", "r") as f:
        for line in f.readlines():
            if line.startswith("-e"):
                continue
            else:
                requirements.append(line)

    with NamedTemporaryFile(mode="w", prefix="req", suffix=".txt") as req_file:
        req_file.writelines(requirements)
        req_file.flush()
        with_constraints = f'--pip-args "--constraint {req_file.name}"'
        sudo(
            f"{GLOBAL_PIPX} install --force projects/{root_project} {with_constraints}",
        )
        if packages:
            packages_str = " ".join(packages)
            sudo(
                f"{GLOBAL_PIPX} inject --include-apps uoft_{root_project} {packages_str} {with_constraints}",
            )


def all_projects():
    return sorted(REPO_ROOT.glob("projects/*"))


def all_projects_by_name():
    return set([p.name for p in all_projects()])


def all_projects_by_name_except_core():
    return all_projects_by_name().symmetric_difference({"core"})