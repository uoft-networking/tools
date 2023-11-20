# Overview

This repository is what's known as a monorepo. It contains multiple projects, each of which is a standalone library or command-line tool (or both). Individual projects are located in the `projects/` directory.

Everything else in this repository is shared infrastructure, such as build scripts, integration tests, developer tools, and documentation.

Getting Started

# Getting started

1. `git clone https://github.com/uoft-networking/tools uoft-tools`
2. `cd uoft-tools`
3. `./run` (this will install [rye](https://rye-up.com/guide/installation/) if you don't already have it, and create a python3.10 virtual environment in `.venv/` with all the projects installed in "editable mode")

## Optional steps

To get the most out of your dev experience in this monorepo, consider the following optional steps you can take:

 - `source .venv/bin/activate` to activate the virtual environment in your current shell
 - Install [direnv](https://direnv.net/) and run `direnv allow .`, so that you don't have to manually activate the virtual environment every time you open a new shell
 - Config your editor to use `.venv/bin/python` as python interpreter (this should be automatically done in VSCode)

## Running tests

This repository is configured to support pytest autodiscovery. Any IDE which supports pytest should be able to run tests without any additional configuration.

You can also run tests from the command line using `./run test-all` or `./run test <project>`.

## Installing packages

To install a project into your regular pipx installation, run `pipx install ./projects/<project>`. 

To install a package globally on your machine, (ex. when installing onto a shared tool server), run `./run global-install <project>`

## Adding a project to the repo

1. `./run new-project <project>`
2. Follow all prompts to create a new project

## Making a new release

All projects in this repository are versioned together. There is a single version number which is shared by all projects. Version info is stored in git tags.

TODO: document project release process
