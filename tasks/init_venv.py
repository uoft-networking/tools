#!/usr/bin/env python

from os import system, environ, chdir
from subprocess import check_output, call, CalledProcessError
import platform

try:
    from __builtin__ import raw_input as input
except ImportError:
    pass

print("Step 1: Ensure python3.10 is installed...")

local_bin = environ["HOME"]+"/.local/bin"
environ['PATH'] += ':'+local_bin

def install_python():
    repo = "https://github.com/indygreg/python-build-standalone"
    tmp = environ.get("TMPDIR", "/tmp")
    data_dir = environ.get("XDG_DATA_HOME", environ['HOME']+"/.local/share")
    target_dir = data_dir+"/python-build-standalone"

    print("python3.10 does not appear to be installed.")
    print("Would you like me to download a standalone copy from '"+repo+"' and save it in "+target_dir+" to install it? [y/N]")
    if input().lower() != "y":
        print("Please install python3.10 using whatever means are available to you (package manager, compile from source, etc).")
        print("Aborting.")
        exit(1)
    print("Attempting to download python3.10...")

    arch = platform.machine()
    arches = {
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "i386": "i686",
    }
    if arch not in arches:
        print("Unsupported architecture: "+arch)
        print("Aborting.")
        exit(1)
    arch = arches[arch]

    os = platform.system()
    oses = {
        "Linux": "_v2-unknown-linux-gnu",
        "Darwin": "-apple-darwin",
        "Windows": "-pc-windows-msvc-shared",
    }
    if os not in oses:
        print("Unsupported OS: "+os)
        print("Aborting.")
        exit(1)
    os = oses[os]

    target_url ='/releases/download/20221002/cpython-3.10.7+20221002-{arch}{os}-install_only.tar.gz'.format(arch=arch, os=os)

    ret = system("curl -L -o "+tmp+"/python3.10.tar.gz "+repo+target_url)
    if ret != 0:
        ret = system("wget -O "+tmp+"/python3.10.tar.gz "+repo+target_url)
        if ret != 0:
            print("Failed to download python3.10.")
            print("Aborting.")
            exit(1)
    system("mkdir -p "+target_dir)

    ret = system("tar -C "+target_dir+" -xzf "+tmp+"/python3.10.tar.gz")
    if ret != 0:
        print("Failed to extract python3.10.")
        print("Aborting.")
        exit(1)
    system("rm "+tmp+"/python3.10.tar.gz")
    system("mkdir -p "+local_bin)
    system("ln -s "+target_dir+"/python/bin/python3.10 "+local_bin+"/python3.10")

try:
    py310 = check_output("which python3.10".split()).strip()
except CalledProcessError:
    install_python()
    py310 = check_output("which python3.10".split()).strip()

print("Step 2: Create .venv...")

system("python3.10 -m venv .venv")
system(". .venv/bin/activate; pip install --upgrade pip")
system(". .venv/bin/activate; pip install --upgrade setuptools wheel")
system(". .venv/bin/activate; pip install --upgrade -r dev.requirements.txt")
system(". .venv/bin/activate; invoke install-all-editable")

    
