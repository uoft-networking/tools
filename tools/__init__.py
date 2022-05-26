from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import run
from datetime import date
from typing import Literal
from zipfile import ZipFile
from tarfile import TarFile
from hashlib import md5
import os
from shutil import rmtree

import tomlkit
import typer


def call(fn_name: str):
    if fn_name not in globals():
        raise Exception(f'Function `{fn_name}` is not defined')
    fn = globals()[fn_name]
    typer.run(fn)


# deprecated
def gather_dependencies():
    """collect dependencies from all projects in this monorepo and add them into the root
    pyproject.toml's dependency list so they can be installed into the monorepo's venv"""
    root = Path("pyproject.toml")
    root_data = tomlkit.loads(root.read_text("utf-8"))

    for project, pyproject_file in _get_projects():
        # if project in ["nautobot"]:
        #     continue
        data = tomlkit.loads(pyproject_file.read_text("utf-8"))
        if "utsc.core" in data["tool"]["poetry"]["dependencies"]:  # type: ignore
            del data["tool"]["poetry"]["dependencies"]["utsc.core"]  # type: ignore
        root_data["tool"]["poetry"]["dependencies"].update(data["tool"]["poetry"]["dependencies"])  # type: ignore

    root.write_text(tomlkit.dumps(root_data), "utf-8")


# deprecated
def update_version(project: str = "core", bump_version: bool = False):  
    version = _get_poetry(project, "version").split(".")

    if bump_version:
        if len(version) > 3:
            version[3] = str(int(version[3]) + 1)
        else:
            version.append("1")
        new_version = ".".join(version)
    else:
        t = date.today()
        new_version = f"{t.year}.{t.month}.{t.day}"

    projects = dict(_get_projects())
    pyproject_file = projects[project]
    pyproject_data = tomlkit.loads(pyproject_file.read_text("utf-8"))
    pyproject_data["tool"]["poetry"]["version"] = new_version  # type: ignore
    pyproject_file.write_text(tomlkit.dumps(pyproject_data))
    print(f'updated "{project}" version to "{new_version}"')


def bump_version(project: str):
    current_version = _get_poetry(project, "version")
    new_version = _bump_version(current_version)
    projects = dict(_get_projects())
    pyproject_file = projects[project]
    pyproject_data = tomlkit.loads(pyproject_file.read_text("utf-8"))
    pyproject_data["tool"]["poetry"]["version"] = new_version  # type: ignore
    pyproject_file.write_text(tomlkit.dumps(pyproject_data))
    print(f'updated "{project}" version from {current_version} to {new_version}')


def build(project: str):
    run("python -m build".split(), cwd=Path("projects/" + project), check=True)


def check_dist_files(project: str):
    project_path = Path(f"projects/{project}")
    dists = project_path / 'dist'
    for package in dists.iterdir():
        print(package, ':')
        if package.suffix == '.whl':
            with ZipFile(package) as z:
                for n in z.namelist():
                    print('    ', n)
        if package.suffix == '.gz':
            with TarFile.open(package) as t:
                for n in t.getnames():
                    print('    ', n)



# deprecated
def build1(project: str, bump_version: bool = False, skip_core: bool = False):
    _get_poetry_builder()
    if project != "core" and not skip_core:
        build("core", bump_version)
    update_version(project, bump_version)
    project_path = Path("projects/" + project).absolute()
    rmtree(project_path/'dist', ignore_errors=True)
    src = Path("src").absolute()
    run(
        f"docker run -it --rm -v {project_path}:/code -v {src}:/code/src utsc-poetry-builder".split(),
        check=True,
    )


def publish(project: str, build_first: bool = False, bump: bool = False, skip_core: bool = False):
    if project != "core" and not skip_core:
        publish("core", build_first, bump)
    if build_first:
        build(project, bump, skip_core)

    match _published_state(project):
        case 'published':
            print(f'This version of "{project}" has already been published, skipping')
        case 'outdated':
            print("A different version of this project has already been published today. I'm going to bump the version and publish")
            publish(project, build_first=True, bump=True, skip_core=skip_core)
        case 'unpublished':
            run("poetry publish".split(), cwd=Path("projects/" + project), check=True)


def fix_shebangs():
    here = Path(__file__).parent
    for file in here.iterdir():
        ftype = (
            run(["file", str(file)], check=True, capture_output=True)
            .stdout.decode()
            .strip()
        )
        if "text executable" not in ftype:
            continue
        contents = file.read_text().splitlines()
        if "python3" in contents[0] and str(here) not in contents[0]:
            print(f"Fixing shebang for {file}")
            contents[0] = "#!/usr/bin/env bash"
            contents.insert(
                1, '"exec" "-a" "$0" "$(dirname $(realpath $0))/python3.10" "$0" "$@"'
            )
            file.write_text("\n".join(contents))


def _get_projects():
    for item in Path("projects/").iterdir():
        if item.is_dir():
            yield item.name, item.joinpath("pyproject.toml")


def _bump_version(curr_version: str):
    current_version = curr_version.split('.')
    today_version = date.today().isoformat().split('-')
    
    # If current version is today's date in calver format, bump it. 
    if current_version[:3] == today_version:
        if len(current_version) == 3:
            target_version = current_version + ['post0']
        else:
            current_post = current_version[3][-1:]
            target_post = str(int(current_post)+1)
            target_version = today_version + ['post'+target_post]

    # Otherwise, set it to today's date
    else:
        target_version = today_version

    return '.'.join(target_version)


def _get_poetry_builder():
    "ensures that docker is installed / available, and builds+tags the 'utsc-poetry-builder' docker image if needed"
    r = run(
        "docker image inspect utsc-poetry-builder:latest".split(),
        check=False,
        capture_output=True,
    )
    match r.returncode:
        case 127:
            raise Exception("`docker` command not found. Please install docker.")
        case 1:
            print("Building `utsc-poetry-builder` image...")
            uid = str(os.geteuid())
            run(
                [
                    "docker",
                    "build",
                    "--build-arg",
                    "uid=" + uid,
                    "-t",
                    "utsc-poetry-builder",
                    "./tools",
                ],
                check=True,
                capture_output=False,
            )
        case 0:
            return
        case _:
            raise Exception(
                "checking for `utsc-poetry-builder` docker image failed unexpectedly:"
                + r.stdout.decode()
                + r.stderr.decode()
            )


def _get_poetry(project: str, key: str) -> str:
    projects = dict(_get_projects())
    pyproject_file = projects[project]
    pyproject_data = tomlkit.loads(pyproject_file.read_text("utf-8"))
    return pyproject_data["tool"]["poetry"][key]  # type: ignore


def _get_pypi_version(project: str):
    with TemporaryDirectory() as tmp:
        run(
            f"pip download --no-deps utsc.{project}".split(),
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        wheel = list(Path(tmp).glob("*.whl"))[0]
        hash = md5(wheel.read_bytes()).hexdigest()
        wheel = ZipFile(wheel)
        meta = next(f for f in wheel.filelist if "METADATA" in f.filename)
        metadata = wheel.read(meta).decode()
        version = next(l for l in metadata.splitlines() if l.startswith("Version: "))
        version = version.partition("Version:")[2].strip()
    return version, hash


def _get_built_wheel(project: str):
    wheels = list(Path(f"projects/{project}/dist").glob("*.whl"))
    match len(wheels):
        case 0:
            raise Exception(
                f"this project does not have any built wheels. Run `poe build {project}` and try again"
            )
        case 1:
            return wheels[0]
        case _:
            raise Exception(
                f'"{project}" project has too many wheels, somehow. please empty dist and try again.'
            )


def _published_state(project: str) -> Literal['unpublished', 'outdated', 'published']:
    local_version = _get_poetry(project, "version")
    local_hash = md5(_get_built_wheel(project).read_bytes()).hexdigest()
    pypi_version, pypi_hash = _get_pypi_version(project)
    if local_version != pypi_version:
        return 'unpublished'
    if local_hash == pypi_hash:
        return 'published'
    return 'outdated'


if __name__ == "__main__":
    # DEBUG CODE HERE
    t = _bump_version('2020.01.01')
    t2 = _bump_version('2022.05.17')
    t3 = _bump_version('2022.05.17.post0')
    t4 = _bump_version('2022.05.17.post3')
    print()
