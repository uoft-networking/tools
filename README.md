a python monorepo for all projects in the utsc-networking umbrella

# Adding a new project to this repo

All distributable code goes into the utsc namespace package in the `src` directory (ie `src/utsc/<project>`)
All tests go into a subdirectory of the `tests` folder (ie `tests/<project>`)
All github workflow files go into the .github/workflows folder, prefixed with the project name
(ie `.github/workflows/<project>.yml` is the default workflow for the project, `.github/workflows/<project>extra.yml` is an additional workflow file, presumably with a different trigger)
Ancilliary project files (ie `poetry.lock` & `pyproject.toml`) go into `projects/<project>`.
each project folder in the `projects` directory must include a `utsc` namespace folder containing a symlink pointing to the project code in the `src` folder at the root of this repo, so that poetry can build pep420-namespaced packages (ie `projects/<project>/utsc/<project>` should symlink to `src/utsc/<project>`)
Each project should implement its own typer cli in `src/utsc/<project>/__main__.py`. Each project's pyproject file (ie `projects/<project>/pyproject.toml`) should contain an entrypoint (or "script", as poetry calls them) that looks something like this:
```toml
[tool.poetry.scripts]
"utsc.<project>" = "utsc.<project>.__main__:cli"
```
