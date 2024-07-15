# About

This package contains a set of utilities useful for building python libraries, scripts, and command-line utilities

This toolkit makes it really easy to write small, simple, well designed CLI utilities
In fact, the aim of this project is to make well-engineered CLIs almost as easy to write and deploy as basic python scripts.
It leverages a lot of really fantastic modern libraries and tools to do so, like *pydantic*, *typer*, and *rich*
It's designed to be easy to include in other projects. all of its mainline dependencies are vendored and all modules which have external un-vendorable dependencies are available as optional extras

# Install

```
pip install uoft_core
```

to include all optional dependencies, run

```
pip install uoft_core[all]
```

### `uoft_core.prompt.Prompt`
In `uoft_core.other` there is a `Prompt` class which can be used to interactively prompt users for input for various types of data. This was a good idea with a poor implementation.
It has been re-written almost entirely from scratch as the `uoft_core.prompt.Prompt` class. 
This new class handles all the same features as the original (tab-completion of choices, automatic history, inline "as-you_type" validation, flexible handling of default values), but also includes a method called `from_model`, with the ability to take in a Pydantic model and interactively prompt for all of its fields.
This new implementation also has the ability to handle password prompts where the previous one couldn't

### CLI Framework / Configuration management
One of the core components of `uoft_core` is the `BaseSettings` class. This class is built on top of Pydantic's [BaseSettings](https://pydantic-docs.helpmanual.io/usage/settings/) and forms the basic framework of all uoft commandline tools. Subclassing the `BaseSettings` class allows you to handle all the common components of writing CLI apps:
 - finding, fetching, loading, and merging config files 
   - user configs overriding site-wide configs 
   - handling configuration in any combination of INI, JSON, YAML, and TOML formats
   - identifying which paths configuration data could be written to
   - loading configuration from default paths following industry standards
   - loading configuration from alternat paths specified by envirnoment vars
   - looking up data in the configuration by key, overridable by environment vars
 - finding /creating CLI-specific cache directories for semi-permanent data
 - argument & command parsing with typer, in a way that integrates with the other features
 - ability to retrieve the final configuration object as a Pydantic Model instance

Example usage:

```python
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from uoft_core import BaseSettings, chomptxt

class Settings(BaseSettings):

    class Config(BaseSettings.Config):
        app_name = 'switchconfig'

    generate: bool

    class Deploy(BaseModel):
        ssh_pass_cmd: str = Field(
            description="shell command to aquire the console server ssh password"
        )
        terminal_pass_cmd: str = Field(
            description="shell command to aquire the switch's terminal access password"
        )
        enable_pass_cmd: str = Field(
            description="shell command to aquire the switch's enable password"
        )
        targets: dict[str, str] = Field(
            description=chomptxt(
                """
                a table / dictionary of console servers, mapping console server 
                names to console server hostname/fqdn+port combinations
                """
            )
        )
        
    deploy: Deploy = Field(
        description="whether to include any overriding configuration related to the deploy command",
    )
    debug: bool = Field(False, description="whether to permanently enable debug mode")

settings = Settings.from_cache()
```

This new framework also leverages the new `Prompt` class from `uoft_core.prompt.Prompt` to interactively prompt for any values not specified in site-wide config files, user-local config files, or environment variables

### YAML
`uoft_core.yaml` is a heavily edited fork of [ruamel.yaml](https://pypi.org/project/ruamel.yaml/) The biggest difference is that I've dropped compatability with python2 and python <3.10, dropped support for non-comment-preserving loading and dumping, removed dead code, added meaningful, useful type hints, simplified the class hierarchy as much as possible, and made the whole thing easier to understand and easier to debug. The work is not yet done, but this first phase is complete, and all relevant tests are passing.
I've also added `loads`and `dumps` functions to `uoft_core.yaml` whose signatures mostly match `json.loads`, `json.dumps`,  `uoft_core.toml.loads`, and `uoft_core.toml.dumps`
This is used as part of the CLI framework to allow for easy loading and dumping of data from/to yaml files

# Dev Workflow

## VSCode debugger
as the number of projects in this repository grows, the number of VSCode debugger configurations needed to test and debug various parts of it grows larger and larger. There is no way to hit a key and search/select from the list of debug configurations. What I've done instead is I've created a single launch configuration that looks like this:

```json
{
    "name": "Python: Select module to debug",
    "type": "python",
    "request": "launch",
    "module": "uoft_core",
    "console": "integratedTerminal",
    "env": {
        "PYDEBUG": "1"
    },
    "justMyCode": false
},
```

This launches the debug selector in `uoft_core.__main__`. The debug selector will prompt you for a module name to load (Ex. `uoft_aruba.cli`), and a list of commandline arguments to insert into sys.argv. It will then look for and run a function inside that module called `_debug` and run that function. You can put anything you want into that function. Here is an example debug function from the `uoft_aruba.cli` module:

```python
# projects/aruba/uoft_aruba/cli.py

...
app = typer.Typer(
    ...
)

def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()

```

In this example, I'm debugging the uoft_aruba cli tool. If I run the debug selector, enter "uoft_aruba.cli" in the module prompt, and enter "cpsec allowlist provision some_file.csv" in the args prompt, it would be equivalent to running "uoft_aruba cpsec allowist provision some_file.csv", but inside of a debugger. This would allow me to debug the `uoft_aruba.cpsec_allowlist.provision` function in the same context as when it's run from the command line in production.

## `uoft_core.debug_cache`
I've added a handy little utility to uoft_core which is great for debugging and testing code which has a long startup (Ex code that loads a bunch of data from an API or SSH session and then processes that data. This `debug_cache`function is a decorator you can add to a function which will save the output of that function to disk the first time that function is run, and then reuse that saved output every subsequent time you run your code. 
What makes this different from other caching decorators is that it only does this inside of debug sessions. When you run this same code in production, the debug cache is not generated or used.

Here's an example:

```python

from uoft_core import debug_cache

@debug_cache
def get_data_from_server():
    # This is a function that you know works, but takes forever and you don't want to re-run it everytime you restart the debugger
    data = {}
    return data

def process_data():
    data = get_data_from_server()
    # Here is the function you want to work on and tweak and debug and re-run again and again

```
