a python monorepo for all projects in the uoft-networking umbrella

# Overview

External project requirements: `monas`

*environment mgmt*: `monas` / `Pipfile`
*task mgmt*: `poethepoet` / `pyproject.toml`
*build frontend / backend*: `hatchling` / `pyproject.toml`
*release mgmt*: `hatch`

# Dev Workflow

## Getting started

1. install python3.10
2. `python3.10 -m pip install monas`
3. `monas install --root`
4. (optionally) `direnv allow .`
5. config your editor to use `.venv/bin/python` as python interpreter (this should be automatically done in VSCode)

## Adding a project to the repo

1. create `src/uoft/<project>/__init__.py`
2. create `projects/<project>/pyproject.toml` (copy one of the existing ones)
5. `pipenv install -e projects/<project>`
6. create `tests/<project>/__init__.py` and additional tests
7. (optionally) create `.github/workflows/<project>.yaml`

## Making a new release

1. check to see if `uoft_core` needs a new release
2. `cd projects/<project>`
3. `pyproject.toml`: update `version` and `uoft_core` dependency version 
4. `python -m build`
5. `hatch publish`


Each project should implement its own typer cli in `__main__.py`. Each project's pyproject file (ie `projects/<project>/pyproject.toml`) should contain an entrypoint (or "script", as poetry calls them) that looks something like this:
```toml
[tool.poetry.scripts]
"uoft.<project>" = "uoft_<project>.__main__:cli"
```
