# uoft_aruba

Collection of utilities for interacting with Aruba infrastructure

## Installation

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_aruba
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
    - `/etc/xdg/uoft-tools/aruba.ini`
    - `/etc/xdg/uoft-tools/aruba.yaml`
    - `/etc/xdg/uoft-tools/aruba.json`
    - `/etc/xdg/uoft-tools/aruba.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/aruba.ini`
    - `~/.config/uoft-tools/aruba.yaml`
    - `~/.config/uoft-tools/aruba.json`
    - `~/.config/uoft-tools/aruba.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/aruba.ini`
    - `/Library/Preferences/uoft-tools/aruba.yaml`
    - `/Library/Preferences/uoft-tools/aruba.json`
    - `/Library/Preferences/uoft-tools/aruba.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/aruba.ini`
    - `~/.config/uoft-tools/aruba.yaml`
    - `~/.config/uoft-tools/aruba.json`
    - `~/.config/uoft-tools/aruba.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/aruba.ini`
    - `~/Library/Preferences/uoft-tools/aruba.yaml`
    - `~/Library/Preferences/uoft-tools/aruba.json`
    - `~/Library/Preferences/uoft-tools/aruba.toml`


    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `ARUBA_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `ARUBA_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-aruba` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.

3. Environment variables. Environment variables are loaded from the `ARUBA_` namespace. For example, the `foo` configuration option can be set by setting the `ARUBA_FOO` environment variable.

Configuration Options:
<!--
[[[cog 
import _cog as c; c.gen_conf_table('uoft_aruba')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| svc_account | str | Aruba API Authentication Account |  |  |
| mm_vrrp_hostname | str | Aruba Mobility Master Primary IP Adress / Hostname |  |  |
| md_hostnames | str | Aruba Controller (Managed Device) IP Adresses / Hostnames |  |  |
| password | SecretStr | Aruba API Authentication Password | Password used to authenticate to the Aruba API. |  |
| default_config_path | str | Aruba API Default Config Path | Default config path used for API requests. Ex /md or /md/UTSC | /md |
<!--[[[end]]] -->

## License

MIT