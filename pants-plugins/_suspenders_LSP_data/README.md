the currently published version of the vscode-suspenders plugin (0.0.3 at the time of writing) has a bug where the __builtins__.pyi file it generates is missing BUILD file symbols.

The latest unreleased version of the plugin at the time of this writing fixes that bug, but produces a __builtins__.pyi file with invalid syntax, and has some other bug preventing completions inside BUILD files from working. 

The files within this directory are the latest generated LSP data, manually corrected by hand to function with the published vscode-suspenders plugin

to install, `cp ./* <repo root>/.pants.d/suspenders