#!/bin/sh
""":"
# Step one: find any working python
for py in python3.10 python3.9 python3.8 python3.7 python3.6 python3.5 python3.4 python3 python python2.7 python2; do
    if command -v "$py" >/dev/null 2>&1; then
        break
    fi
done

# Step two: run this script with that python
exec "$py" "$0" "$@"
"""
__doc__ = """Python3.10 bootstrapping script

The purpose of this script is to enable easy management of python3.10 and 
python3.10-based virtual environments with pipx or venv.

This script is written with maximum compatability in mind. 
It should run on Python 3.3+ (including Python 2.7), and should work on MacOS, Windows with WSL2, 
and any linux distro (except MUSL distros like Alpine, These are not supported yet).

Examples:
    ensure-python.py
      # Check to see if python3.10 is installed and prompt to install if not

    ensure-python.py install python
      # Install python3.10 to ~/.local/share/python-build-standalone/python3.10, symlink it to ~/.local/bin

    ensure-python.py --global install python
      # Install python3.10 to /opt/python-build-standalone/python3.10, symlink it to /usr/local/bin
      # You will need to run this script as root

    ensure-python.py install pipx
      # Install pipx in the local python3.10 installation, symlink it to ~/.local/bin 
      # (also installs python3.10 standalone if needed)

    ensure-python.py --global install pipx
      # Install pipx in the global python3.10 installation, symlink it to /usr/local/bin 
      # (also installs python3.10 standalone if needed)
      # You will need to run this script as root

    ensure-python.py install venv
      # Create a virtual environment called .venv in the current working directory 
      # (also installs python3.10 standalone if needed)

    ensure-python.py --global install venv
      # Create a virtual environment in /opt. You will be prompted to name the environment. 
      # (also installs python3.10 standalone if needed)
      # You will need to run this script as root
"""

import argparse
import platform
import ssl
import sys
import tarfile
from os import environ, path, makedirs, remove, rename, readlink, chmod
from subprocess import check_output
from textwrap import dedent

try:
    # Python 2.7
    from __builtin__ import raw_input as input  # type: ignore
except ImportError:
    # Python 3.3+
    pass

try:
    # Python 3
    from urllib.error import URLError
    from urllib.request import urlopen
except ImportError:
    # Python 2
    from urllib2 import URLError, urlopen  # type: ignore pylint: disable=import-error


REPO = "https://github.com/indygreg/python-build-standalone"
RELEASE = 20230726
DOWNLOAD_VERSION = "3.10.12"
TMP = environ.get("TMPDIR", "/tmp")
ARCHIVE_FILE = TMP + "/python-build-standalone-" + DOWNLOAD_VERSION + ".tar.gz"
LOCAL_BIN = environ["HOME"] + "/.local/bin"
GLOBAL_BIN = "/usr/local/bin"
DATA_DIR = environ.get("XDG_DATA_HOME", environ["HOME"] + "/.local/share")
LOCAL_INSTALL_DIR = DATA_DIR + "/python-build-standalone"
GLOBAL_INSTALL_DIR = "/opt/python-build-standalone"
LOCAL_PIPX_HOME = LOCAL_INSTALL_DIR + "/pipx"  # PIPX_HOME is where the virtualenvs pipx creates will live
GLOBAL_PIPX_HOME = GLOBAL_INSTALL_DIR + "/pipx"


def pr(msg):
    sys.stderr.write(msg + "\n")


def main():
    if len(sys.argv) == 1:
        # No arguments
        print(ensure_python())
        sys.exit(0)

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "action",
        choices=["install"],
        help="which action to take on a target (currently only 'install' is supported)",
    )  # TODO: add 'uninstall' and 'update' options
    p.add_argument(
        "target",
        choices=["python", "pipx", "venv"],
        help="target to install (currently only 'python', 'pipx', and 'venv' are supported)",
    )
    p.add_argument("--global", action="store_true", help="[un]install [target] globally")
    args = p.parse_args()
    global_ = vars(args)["global"]  # type: bool
    if args.action == "install":
        if args.target == "python":
            print(install_python(global_))
        elif args.target == "pipx":
            print(install_pipx(global_))
        elif args.target == "venv":
            create_venv(global_)


def ensure_python(global_=False):
    """Ensure that python3.10 is installed and return the path to the python3.10 executable"""
    pr("Checking to see if python3.10 is installed...")

    if global_:
        install_dir = GLOBAL_INSTALL_DIR
        bin_dir = GLOBAL_BIN
    else:
        install_dir = LOCAL_INSTALL_DIR
        bin_dir = LOCAL_BIN
        if bin_dir not in environ["PATH"]:
            pr(bin_dir + " is not in your PATH...")
            pr("Please consider permanently adding this to your PATH.")
            pr("You can do this by adding the following line to your shell config file (e.g. ~/.bashrc):")
            pr("export PATH=$PATH:" + bin_dir)

    if (
        path.exists(install_dir + "/python3.10/bin/python3.10")
        and path.exists(bin_dir + "/python3.10")
        and (readlink(bin_dir + "/python3.10") == install_dir + "/python3.10/bin/python3.10")
    ):
        pr("SUCCESS! Python3.10 is installed.")
        return bin_dir + "/python3.10"

    py310 = install_python(global_, prompt=True)
    return py310


def install_python(global_=False, prompt=False):
    """Install python3.10 standalone and return the path to the python3.10 executable"""

    if global_:
        install_dir = GLOBAL_INSTALL_DIR
        bin_dir = GLOBAL_BIN
    else:
        install_dir = LOCAL_INSTALL_DIR
        bin_dir = LOCAL_BIN

    if prompt:
        pr(
            "Would you like me to download a standalone copy from '"
            + REPO
            + "' and install it in "
            + LOCAL_INSTALL_DIR
            + "[Y/n]"
        )
        if input().lower() not in ["y", ""]:
            pr("Aborting.")
            sys.exit(1)

    pr("Installing python3.10...")

    archive_file = _download_python()

    pr("Extracting python3.10 to " + install_dir + "...")
    makedirs(install_dir, exist_ok=True)

    with tarfile.open(archive_file, "r:gz") as tar:
        tar.extractall(install_dir)
    remove(archive_file)

    # The portable python3.10 archive contains a directory called python, we need to rename it to python3.10"
    rename(install_dir + "/python", install_dir + "/python3.10")

    installed_python = install_dir + "/python3.10/bin/python3.10"

    pr("Symlinking " + installed_python + " to " + bin_dir + "...")
    makedirs(bin_dir, exist_ok=True)
    py310 = bin_dir + "/python3.10"
    check_output(["ln", "-sf", installed_python, py310])

    pr(
        "SUCCESS! Python3.10 has been installed into {}\nwith a symlink {} -> {}.".format(
            install_dir, py310, installed_python
        )
    )
    return py310


def install_pipx(global_=False):
    pr("Installing pipx...")

    if global_:
        bin_dir = GLOBAL_BIN
        install_dir = GLOBAL_INSTALL_DIR
        pipx_home = GLOBAL_PIPX_HOME
    else:
        bin_dir = LOCAL_BIN
        install_dir = LOCAL_INSTALL_DIR
        pipx_home = LOCAL_PIPX_HOME

    py310 = ensure_python()
    check_output([py310, "-m", "pip", "install", "pipx"])

    pr("creating pipx wrapper script...")
    pipx = install_dir + "/python3.10/bin/pipx"
    pipx_wrapper = bin_dir + "/pipx"
    with open(pipx_wrapper, "w") as f:
        f.write(
            dedent(
                """\
                #!/bin/sh
                export PIPX_HOME={}
                export PIPX_BIN_DIR={}
                exec {} "$@"
                """.format(
                    pipx_home, bin_dir, pipx
                )
            )
        )
    chmod(pipx_wrapper, 0o755)

    return pipx_wrapper


def create_venv(install_path=None):
    """Create a virtualenv at a given path, relative to the current directory"""
    if not install_path:
        install_path = input("Enter the name/path of the virtual environment (default='.venv'): ")
        if not install_path:
            install_path = ".venv"
    install_path = path.abspath(install_path)
    py310 = ensure_python()

    pr("Creating {}...".format(install_path))
    check_output([py310, "-m", "venv", install_path])

    pr("Upgrade-installing pip into the virtual environment...")
    check_output([install_path + "/bin/pip", "install", "--upgrade", "pip"])

    pr("Upgrade-installing [setuptools, wheel, invoke] into the virtual environment...")
    check_output(
        [
            install_path + "/bin/pip",
            "install",
            "--upgrade",
            "setuptools",
            "wheel",
            "invoke",
        ]
    )

    pr("SUCCESS! Virtual environment created at {}".format(install_path))
    return install_path


def _download_python():
    """Download the python3.10 standalone archive and return the path to the archive file"""

    pr("Attempting to download python3.10...")

    url = _get_url()
    _download_file(url, ARCHIVE_FILE)

    pr("Downloaded python3.10 archive to " + ARCHIVE_FILE)
    return ARCHIVE_FILE


def _get_url():
    """Compute a URL pointing to the correct archive file for python3.10 on the current os/architecture"""
    arch = platform.machine()
    arches = {
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "i386": "i686",
    }
    try:
        arch = arches[arch]
    except KeyError:
        pr("Unsupported architecture: " + arch)
        pr("Aborting.")
        sys.exit(1)

    os = platform.system()
    oses = {
        "Linux": "_v2-unknown-linux-gnu",
        "Darwin": "-apple-darwin",
        "Windows": "-pc-windows-msvc-shared",
    }
    try:
        os = oses[os]
    except KeyError:
        pr("Unsupported OS: " + os)
        pr("Aborting.")
        sys.exit(1)

    url_template = "/releases/download/{release}/cpython-{download_version}+{release}-{arch}{os}-install_only.tar.gz"
    target = url_template.format(arch=arch, os=os, release=RELEASE, download_version=DOWNLOAD_VERSION)
    url = REPO + target
    return url


def _download_file(url, dest):
    """Download a file from a URL and write it to a path on disk"""
    pr("Downloading " + url + "...")
    try:
        response = urlopen(url)
        data = response.read()
    except URLError:
        # Python can't find CA certs, try again without SSL verification
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.verify_mode = ssl.CERT_NONE
        response = urlopen(url, context=context)
        data = response.read()
    with open(dest, "wb") as out_file:
        out_file.write(data)


if __name__ == "__main__":
    main()
