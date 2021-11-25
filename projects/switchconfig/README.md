This tool uses the Jinja template language to instantiate switch configs for new switches from a set of base templates

# Instalation

This tool is designed to run on Linux, MacOS, and Windows Subsystem for Linux (a.k.a. WSL)

Option #1: Homebrew
```
brew tap utsc-networking/tools https://github.com/utsc-networking/utsc-tools
brew install utsc-networking/tools/utsc.switchconfig
```

Option #2: A portable python distribution
```
wget https://github.com/utsc-networking/utsc-tools/releases/download/utsc-tools-v0.0.2/utsc-tools-`uname`-`uname -m`.tar.gz
tar -xvf utsc-tools-`uname`-`uname -m`.tar.gz

# this will create a folder called utsc-tools. you can move this folder anywhere you like on your system
# Example:
sudo mv utsc-tools /opt/

# and then install the switchconfig tool into the distribution
# Example:
sudo /opt/utsc-tools/bin/pip3 install utsc.switchconfig
sudo /opt/utsc-tools/bin/fix-shebangs.py

# and finally, symlink the switchconfig tool into you PATH
# Example:
sudo ln -s /opt/utsc-tools/bin/utsc.switchconfig /usr/local/bin/

# You can also, optionally, unpack this distribution into your home folder, if you can't or don't want to install it into /opt.
# you can follow these same steps, but use a path like ~/.local/opt instead of /opt
```