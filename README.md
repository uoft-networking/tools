a python monorepo for all projects in the utsc-networking umbrella

# Overview

External project requirements: `pipenv`

*environment mgmt*: `pipenv` / `Pipfile`
*task mgmt*: `poethepoet` / `pyproject.toml`
*build frontend / backend*: `hatchling` / `pyproject.toml`
*release mgmt*: `hatch`

# Dev Workflow

## Getting started

1. install pipenv
2. install python3.10
3. `pipenv install -d`
4. `pipenv shell`
5. config your editor to use `.venv/bin/python`as python interpreter (this should be automatically done in VSCode)

## Adding a project to the repo

1. create `src/utsc/<project>/__init__.py`
2. create `projects/<project>/pyproject.toml` (copy one of the existing ones)
3. create `projects/<project>/utsc`
4. `cd projects/<project>/utsc && ln -s ../../../src/utsc/<project> ./ && cd ../../..`
5. `pipenv install -e projects/<project>`
6. create `tests/<project>/__init__.py` and additional tests
7. (optionally) create `.github/workflows/<project>.yaml`

## Making a new release

1. check to see if `utsc.core` needs a new release
2. `cd projects/<project>`
3. `pyproject.toml`: update `version` and `utsc.core` dependency version 
4. `python -m build`
5. `hatch publish`


Each project should implement its own typer cli in `src/utsc/<project>/__main__.py`. Each project's pyproject file (ie `projects/<project>/pyproject.toml`) should contain an entrypoint (or "script", as poetry calls them) that looks something like this:
```toml
[tool.poetry.scripts]
"utsc.<project>" = "utsc.<project>.__main__:cli"
```
