#!/usr/bin/env python
""" Python3.10 bootstrapping script
The purpose of this script is to ensure that python3.10 is installed, or install a standalone copy if it is not,
and to optionally use that python version to install pipx or create a virtual environment.

This script is written with maximum compatability in mind. 
It should run on Python 3.3+ (including Python 2.7), and should work on MacOS, Windows with WSL2, and any linux distro (except MUSL distros like Alpine).

If python3.10 isn't installed or isn't usable, you will be given the option to download a standalone copy
This standalone copy will be installed in ~/.local/share/python-build-standalone/python3.10

Usage:
    ./ensure-python.py --help  # Show this help message
    ./ensure-python.py         # find python3.10 on PATH, install python3.10 standalone in your home directory if needed
    ./ensure-python.py venv    # Create a virtual environment in .venv (also installs python3.10 standalone if needed)
    ./ensure-python.py pipx    # Install pipx (also installs python3.10 standalone if needed)
"""

from os import system, environ
from subprocess import check_output, CalledProcessError
import sys
import platform
import tarfile
import ssl

try:
    # Python 2.7
    from __builtin__ import raw_input as input  # type: ignore pylint: disable=redefined-builtin
except ImportError:
    # Python 3.3+
    pass

try:
    # Python 3.3+
    from shutil import which as find_executable
except ImportError:
    # Python 2.7
    from distutils.spawn import find_executable  # type: ignore pylint: disable=deprecated-module

try: 
    # Python 3
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    # Python 2
    from urllib2 import urlopen, URLError # type: ignore pylint: disable=import-error


LOCAL_BIN = environ["HOME"]+"/.local/bin"
REPO = "https://github.com/indygreg/python-build-standalone"
RELEASE = 20221002
DOWNLOAD_VERSION = '3.10.7'
TMP = environ.get("TMPDIR", "/tmp")
ARCHIVE_FILE = TMP+"/python-build-standalone-"+DOWNLOAD_VERSION+".tar.gz"
DATA_DIR = environ.get("XDG_DATA_HOME", environ['HOME']+"/.local/share")
INSTALL_DIR = DATA_DIR+"/python-build-standalone"


def pr(msg):
    sys.stderr.write(msg+"\n")

def ensure_python():
    pr("Checking to see if python3.10 is installed and usable...")

    if LOCAL_BIN not in environ["PATH"]:
        pr("Adding "+LOCAL_BIN+" to PATH...")
        pr("Please consider permanently adding this to your PATH.")
        pr("You can do this by adding the following line to your shell config file (e.g. ~/.bashrc):")
        pr("export PATH=$PATH:"+LOCAL_BIN)
        environ["PATH"] += ":"+LOCAL_BIN
    py310 = find_executable("python3.10")
    if py310:
        pr("python3.10 found at "+py310)
        pr("Checking to see if it is usable...")
        try:
            check_output([py310, "-m", "pip"])
            pr("Yes, python3.10 is usable.")
            return py310
        except CalledProcessError:
            pr(py310+" doesn not appear to include pip and is therefore unusable.")
    else:
        pr("python3.10 does not appear to be installed.")
    
    py310 = install_python()
    return py310
    

def install_python():

    pr("Would you like me to download a standalone copy from '"+REPO+"' and save it in "+INSTALL_DIR+" to install it? [y/N]")
    if input().lower() != "y":
        pr("Please install python3.10 using whatever means are available to you (package manager, compile from source, etc).")
        pr("Aborting.")
        exit(1)
    
    archive_file = download_python()

    pr("Extracting python3.10 to "+INSTALL_DIR+"...")
    check_output(["mkdir", "-p", INSTALL_DIR])

    with tarfile.open(archive_file, 'r:gz') as tar:
        tar.extractall(INSTALL_DIR)
    check_output(["rm", archive_file])

    # The portable python3.10 archive contains a directory called python, we need to rename it to python3.10"
    check_output(["mv", INSTALL_DIR+"/python", INSTALL_DIR+"/python3.10"])

    installed_python = INSTALL_DIR + "/python3.10/bin/python3.10"

    pr("Symlinking "+installed_python+" to "+LOCAL_BIN+"...")
    check_output(["mkdir", "-p", LOCAL_BIN])
    py310 = LOCAL_BIN+"/python3.10"
    check_output(["ln", "-sf", installed_python, py310])
    return py310

def download_python():
    pr("Attempting to download python3.10...")

    arch = platform.machine()
    arches = {
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "i386": "i686",
    }
    try:
        arch = arches[arch]
    except KeyError:
        pr("Unsupported architecture: "+arch)
        pr("Aborting.")
        exit(1)

    os = platform.system()
    oses = {
        "Linux": "_v2-unknown-linux-gnu",
        "Darwin": "-apple-darwin",
        "Windows": "-pc-windows-msvc-shared",
    }
    try:
        os = oses[os]
    except KeyError:
        pr("Unsupported OS: "+os)
        pr("Aborting.")
        exit(1)

    url_template = '/releases/download/{release}/cpython-{download_version}+{release}-{arch}{os}-install_only.tar.gz'
    target = url_template.format(arch=arch, os=os, release=RELEASE, download_version=DOWNLOAD_VERSION)
    url = REPO + target

    pr("Downloading "+url+"...")
    download_file(url, ARCHIVE_FILE)

    pr("Downloaded python3.10 archive to "+ARCHIVE_FILE)
    return ARCHIVE_FILE

def download_file(url, dest):
    pr("Downloading "+url+"...")
    try:
        response = urlopen(url)
        data = response.read()
    except URLError:
        # Python can't find CA certs, try again without SSL verification
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.verify_mode = ssl.CERT_NONE
        response = urlopen(url, context=context)
        data = response.read()
    with open(dest, 'wb') as out_file:
        out_file.write(data)


def create_venv():
    py310 = ensure_python()
    print("Creating .venv...")

    check_output([py310, "-m", "venv", ".venv"])
    check_output([".venv/bin/pip", "install", "--upgrade", "pip"])
    check_output([".venv/bin/pip", "install", "--upgrade", "setuptools", "wheel"])

def install_pipx():
    print("Installing pipx...")

    py310 = ensure_python()
    check_output([py310, "-m", "pip", "install", "--user", "pipx"])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "venv":
            create_venv()
        elif sys.argv[1] == "pipx":
            install_pipx()
        else:
            print(__doc__)
    else:
        py310 = ensure_python()
        print(py310)