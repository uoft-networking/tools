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
