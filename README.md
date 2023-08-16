# Overview

This repository is what's known as a monorepo. It contains multiple projects, each of which is a standalone library or command-line tool (or both). Individual projects are located in the `projects/` directory.

Everything else in this repository is shared infrastructure, such as build scripts, integration tests, developer tools, and documentation.

Getting Started

# Getting started

1. `git clone https://github.com/uoft-networking/tools uoft-tools`
2. `cd uoft-tools`
3. `tasks/ensure-python.py install venv` (this will install a standalone copy of python3.10 if you don't already have it, and create a python3.10 virtual environment in `.venv/`)
4. `source .venv/bin/activate` to activate the virtual environment in your current shell
4. (optionally) install [direnv](https://direnv.net/) and run `direnv allow .`, so that you don't have to manually activate the virtual environment every time you open a new shell
5. `pip install -r dev.requirements.txt` to install the dev tools needed to work on this repository
6. `invoke list-projects` to see a list of all projects
7. `invoke install-editable <project>` to start developing/debugging a particular project, or `invoke install-editable-all` to install all projects in editable mode
8. config your editor to use `.venv/bin/python` as python interpreter (this should be automatically done in VSCode)
9. Add `export MY_BRANCH=dev-<your branch name>` to your `.bashrc` or `.zshrc` file, so that you can use `invoke git.*` commands without having to specify a branch name every time

## Running tests

This repository is configured to support pytest autodiscovery. Any IDE which supports pytest should be able to run tests without any additional configuration.

You can also run tests from the command line using `invoke test-all` or `invoke test <project>`.

## Building packages

To build a package, run `invoke build <project>`. This will create a wheel file and an sdist file in `dist/`.
You can then install the package using `pip install dist/<package>.whl` or `pip install dist/<package>.tar.gz`.

You can also build all packages at once using `invoke build-all`.

## Adding a project to the repo

1. `invoke new-project <project>`
2. Follow all prompts to create a new project

## Making a new release

All projects in this repository are versioned together. There is a single version number which is shared by all projects. Version info is stored in git tags. To make a new release, follow these steps:
1. `invoke changes-since-last-tag` to see if a new release is needed
2. `invoke version-next` and follow the prompts to bump the version number
3. `invoke build-all` to build all packages
4. TODO: `invoke publish-all` to publish all packages to PyPI

# Notes

Each project should implement its own typer cli in `cli.py`. Each project's pyproject file (ie `projects/<project>/pyproject.toml`) should contain an entrypoint that looks something like this:
```toml
[project.scripts]
"uoft-<project>" = "uoft_<project>.cli:cli"
```
