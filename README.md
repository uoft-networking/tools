a python monorepo for all projects in the utsc-networking umbrella

# Adding a new project to this repo

Each project in this repo should have a `projects/<project>` folder.
each project folder in the `projects` directory must include a `src/utsc/<project>` folder in which to store source code for the project. each such project source folder should be symlinked into the central `src/utsc/` directory at the root of this repo (ie `src/utsc/<project>` should be a symlink to `projects/<project>/src/utsc/<project>`)
All tests go into a subdirectory of the `tests` folder (ie `tests/<project>`)
All github workflow files go into the .github/workflows folder, prefixed with the project name
(ie `.github/workflows/<project>.yml` is the default workflow for the project, `.github/workflows/<project>extra.yml` is an additional workflow file, presumably with a different trigger).

Each project should implement its own typer cli in `src/utsc/<project>/__main__.py`. Each project's pyproject file (ie `projects/<project>/pyproject.toml`) should contain an entrypoint (or "script", as poetry calls them) that looks something like this:
```toml
[tool.poetry.scripts]
"utsc.<project>" = "utsc.<project>.__main__:cli"
```
