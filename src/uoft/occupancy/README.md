# uoft_occupancy

Occupancy tracking

## Installation

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_occupancy
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
    - `/etc/xdg/uoft-tools/occupancy.ini`
    - `/etc/xdg/uoft-tools/occupancy.yaml`
    - `/etc/xdg/uoft-tools/occupancy.json`
    - `/etc/xdg/uoft-tools/occupancy.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/occupancy.ini`
    - `~/.config/uoft-tools/occupancy.yaml`
    - `~/.config/uoft-tools/occupancy.json`
    - `~/.config/uoft-tools/occupancy.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/occupancy.ini`
    - `/Library/Preferences/uoft-tools/occupancy.yaml`
    - `/Library/Preferences/uoft-tools/occupancy.json`
    - `/Library/Preferences/uoft-tools/occupancy.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/occupancy.ini`
    - `~/.config/uoft-tools/occupancy.yaml`
    - `~/.config/uoft-tools/occupancy.json`
    - `~/.config/uoft-tools/occupancy.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/occupancy.ini`
    - `~/Library/Preferences/uoft-tools/occupancy.yaml`
    - `~/Library/Preferences/uoft-tools/occupancy.json`
    - `~/Library/Preferences/uoft-tools/occupancy.toml`


    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `OCCUPANCY_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `OCCUPANCY_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-occupancy` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.

3. Environment variables. Environment variables are loaded from the `OCCUPANCY_` namespace. For example, the `foo` configuration option can be set by setting the `OCCUPANCY_FOO` environment variable.

Configuration Options:
<!--
[[[cog 
import _cog as c; c.gen_conf_table('uoft_occupancy')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| psql_database | str |  |  | annotation=NoneType required=True title='PSQL Database name' description='The username used to manage the PSQL database.' |
| psql_host | str |  |  | annotation=NoneType required=True title='PSQL hostname' description='The hostname of the PSQL database.' |
| psql_user | str |  |  | annotation=NoneType required=True title='PSQL username' description='The username used to manage the PSQL database.' |
| psql_password | SecretStr |  |  | annotation=NoneType required=True title='PSQL database password' description='The password used to manage the PSQL database.' |
| psql_port | str |  |  | annotation=NoneType required=True title='PSQL database port' description='The port for the database on the host' |
| aruba_svc_account | str |  |  | annotation=NoneType required=True title='Aruba API Authentication Account' description="Account used to log into the API of Aruba 'Managed Devices'." |
| aruba_svc_password | SecretStr |  |  | annotation=NoneType required=True title='Aruba API Authentication Password' description="Password used to log into the API of Aruba 'Managed Devices'." |
| aruba_md_hostnames | str |  |  | annotation=NoneType required=True title='Aruba Controller (Managed Device) IP Adresses / Hostnames' description='A list of Aruba MD names to query.' |
| aruba_default_config_path | str |  |  | annotation=NoneType required=True title='Aruba API Default Config Path' description="Default config path used for API requests of Aruba 'Managed Devices'." |
| global_ranges | str |  |  | annotation=NoneType required=True title='Global column ranges' description='List used in conjunction with unique users.' |
| filter_ranges | str |  |  | annotation=NoneType required=True title='Global filter ranges' description='Used to count unique users.' |
| departments | Department |  |  | annotation=NoneType required=True title='Departmental Models' description='Any number of departmental models can be created as long as they follow the class format defined.' |
<!--[[[end]]] -->

## License

MIT