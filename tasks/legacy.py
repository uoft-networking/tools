"""commands ported over from this monorepo's old adhoc task runner"""

from pathlib import Path
from invoke import task, Context
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

@task()
def build_base(ctx: Context, project: str = "all"):
    """write a bash script to a tempfile and execute it with ctx.run"""
    tempfile = Path("./tempfile")
    tempfile.write_text(
        """
        #!/usr/bin/env bash

        set -euo pipefail

        echo "Initializing..."
        build_date="20211017"
        build_time="1616"
        declare -A os=(["Darwin"]="apple-darwin" ["Linux"]='unknown-linux-gnu')
        os="${os[`uname`]}"
        declare -A arch=(["arm64"]="aarch64" ["x86_64"]="x86_64")
        arch="${arch[`uname -m`]}"
        tar_file="cpython-3.10.0-${arch}-${os}-pgo+lto-${build_date}T${build_time}.tar"
        tarz_file="${tar_file}.zst"
        url="https://github.com/indygreg/python-build-standalone/releases/download/${build_date}/${tarz_file}"

        cd dist
        test -f build.log && rm build.log
        test ! -f "${tarz_file}" && echo "Fetching portable python build from indygreg/python-build-standalone" && wget "${url}" &>> build.log
        test ! -f "${tar_file}" && echo "Decompressing zstd archive..." && zstd -d "${tarz_file}" &>> build.log

        echo "Unpacking decompressed tar file..."
        tar -xvf "${tar_file}" &>> build.log
        test -d uoft-tools && rm -r uoft-tools

        echo "Prepping uoft-tools python distribution..."
        mkdir uoft-tools
        mv python/install/* uoft-tools/
        cp ../scripts/fix-shebangs.py uoft-tools/bin/

        echo "installing 'uoft' python package into distribution..."
        uoft-tools/bin/pip install uoft_core &>> build.log
        uoft-tools/bin/fix-shebangs.py
        echo "Packing uoft-tools distribution into gzip-compressed archive..."
        tar -czvf "uoft-tools-$(uname)-$(uname -m).tar.gz" uoft-tools/ &>> build.log

        echo "Done!"
        """,
        encoding="utf-8",
    )
    ctx.run(f"bash {tempfile}")
    tempfile.unlink()
    
@task()
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
        if "uoft_core" in data["tool"]["poetry"]["dependencies"]:  # type: ignore
            del data["tool"]["poetry"]["dependencies"]["uoft_core"]  # type: ignore
        root_data["tool"]["poetry"]["dependencies"].update(data["tool"]["poetry"]["dependencies"])  # type: ignore

    root.write_text(tomlkit.dumps(root_data), "utf-8")


# deprecated
def update_version(project: str, bump_version: bool = False):  
    version = _get_metadata(project, "version").split(".")

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
    pyproject_data["project"]["version"] = new_version  # type: ignore
    pyproject_file.write_text(tomlkit.dumps(pyproject_data))
    print(f'updated "{project}" version to "{new_version}"')


def bump_version(project: str):
    projects = dict(_get_projects())
    pyproject_file = projects[project]
    pyproject_data = tomlkit.loads(pyproject_file.read_text("utf-8"))

    current_version = pyproject_data["project"]["version"]  # type: ignore
    new_version = _bump_version(current_version)
    
    pyproject_data["project"]["version"] = new_version  # type: ignore
    pyproject_file.write_text(tomlkit.dumps(pyproject_data))
    print(f'updated "{project}" version from {current_version} to {new_version}')


def build(project: str):
    run("rm -rf dist".split(), cwd=Path("projects/" + project), check=True)
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
        f"docker run -it --rm -v {project_path}:/code -v {src}:/code/src uoft_poetry-builder".split(),
        check=True,
    )


def publish(project: str, build_first: bool = False, bump: bool = False, skip_core: bool = False):
    if project != "core" and not skip_core:
        publish("core", build_first, bump)
    if build_first:
        build1(project, bump, skip_core)

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
    "ensures that docker is installed / available, and builds+tags the 'uoft_poetry-builder' docker image if needed"
    r = run(
        "docker image inspect uoft_poetry-builder:latest".split(),
        check=False,
        capture_output=True,
    )
    match r.returncode:
        case 127:
            raise Exception("`docker` command not found. Please install docker.")
        case 1:
            print("Building `uoft_poetry-builder` image...")
            uid = str(os.geteuid())
            run(
                [
                    "docker",
                    "build",
                    "--build-arg",
                    "uid=" + uid,
                    "-t",
                    "uoft_poetry-builder",
                    "./tools",
                ],
                check=True,
                capture_output=False,
            )
        case 0:
            return
        case _:
            raise Exception(
                "checking for `uoft_poetry-builder` docker image failed unexpectedly:"
                + r.stdout.decode()
                + r.stderr.decode()
            )


def _get_metadata(project: str, key: str) -> str:
    projects = dict(_get_projects())
    pyproject_file = projects[project]
    pyproject_data = tomlkit.loads(pyproject_file.read_text("utf-8"))
    return pyproject_data["project"][key]  # type: ignore


def _get_pypi_version(project: str):
    with TemporaryDirectory() as tmp:
        run(
            f"pip download --no-deps uoft_{project}".split(),
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
    local_version = _get_metadata(project, "version")
    local_hash = md5(_get_built_wheel(project).read_bytes()).hexdigest()
    pypi_version, pypi_hash = _get_pypi_version(project)
    if local_version != pypi_version:
        return 'unpublished'
    if local_hash == pypi_hash:
        return 'published'
    return 'outdated'