# uoft_paloalto

CLI and API to work with Paloalto products (NSM, etc)

## Installation

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_paloalto
```

If you don't have or cannot easily get python3.10, you can run the following commands to download a standalone python3.10 binary and use it to install pipx:

```console
$ curl -L https://github.com/uoft-networking/tools/releases/download/1.1.0/ensure-python.py

$ python ensure-python.py pipx
# You can use python2 or python3 to run this script

```

### Windows

Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) and the [Windows Terminal](https://apps.microsoft.com/store/detail/windows-terminal/9N0DX20HK701?hl=en-ca&gl=ca) and then follow the instructions for MacOS / Linux above.

## Configuration

Configuration for this application is loaded from multiple sources. All configuration from all sources is merged together. In the event of configuration conflicts, the configuration from the last source will take precedence.

Configuration is loaded from the following sources in order:

1. Configuration files in the following locations:
    Linux:
    - `/etc/xdg/uoft-tools/shared.ini`
    - `/etc/xdg/uoft-tools/shared.yaml`
    - `/etc/xdg/uoft-tools/shared.json`
    - `/etc/xdg/uoft-tools/shared.toml`
    - `/etc/xdg/uoft-tools/paloalto.ini`
    - `/etc/xdg/uoft-tools/paloalto.yaml`
    - `/etc/xdg/uoft-tools/paloalto.json`
    - `/etc/xdg/uoft-tools/paloalto.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/paloalto.ini`
    - `~/.config/uoft-tools/paloalto.yaml`
    - `~/.config/uoft-tools/paloalto.json`
    - `~/.config/uoft-tools/paloalto.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/paloalto.ini`
    - `/Library/Preferences/uoft-tools/paloalto.yaml`
    - `/Library/Preferences/uoft-tools/paloalto.json`
    - `/Library/Preferences/uoft-tools/paloalto.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/paloalto.ini`
    - `~/.config/uoft-tools/paloalto.yaml`
    - `~/.config/uoft-tools/paloalto.json`
    - `~/.config/uoft-tools/paloalto.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/paloalto.ini`
    - `~/Library/Preferences/uoft-tools/paloalto.yaml`
    - `~/Library/Preferences/uoft-tools/paloalto.json`
    - `~/Library/Preferences/uoft-tools/paloalto.toml`


    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `PALOALTO_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `PALOALTO_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-paloalto` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.

3. Environment variables. Environment variables are loaded from the `PALOALTO_` namespace. For example, the `foo` configuration option can be set by setting the `PALOALTO_FOO` environment variable.

Configuration Options:
<!--
[[[cog 
import _cog as c; c.gen_conf_table('uoft_paloalto')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| url | str | URL | The base URL of the Palo Alto REST API server. (ex. https://paloalto.example.com) |  |
| username | str | Username | The username to authenticate with the Palo Alto REST API server. |  |
| password | SecretStr | Password | The password to authenticate with the Palo Alto REST API server. |  |
| api_key | SecretStr | API Key | API key to authenticate with the Palo Alto XML API server. Leave blank if you want to generate one later |  |
| device_group | str | Device Group | The device group to use when managing objects. If not provided, objects will be placed in the 'shared' location. |  |
| create_missing_tags | bool | Create Missing Tags | If enabled, missing tags assigned to objects will be created automatically. |  |
<!--[[[end]]] -->

## License

MIT