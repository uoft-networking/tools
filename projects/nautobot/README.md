# uoft_nautobot

A collection of UofT-specific modifications and extensions to Nautobot

## Installation

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_nautobot
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
    - `/etc/xdg/uoft-tools/nautobot.ini`
    - `/etc/xdg/uoft-tools/nautobot.yaml`
    - `/etc/xdg/uoft-tools/nautobot.json`
    - `/etc/xdg/uoft-tools/nautobot.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/nautobot.ini`
    - `~/.config/uoft-tools/nautobot.yaml`
    - `~/.config/uoft-tools/nautobot.json`
    - `~/.config/uoft-tools/nautobot.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/nautobot.ini`
    - `/Library/Preferences/uoft-tools/nautobot.yaml`
    - `/Library/Preferences/uoft-tools/nautobot.json`
    - `/Library/Preferences/uoft-tools/nautobot.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/nautobot.ini`
    - `~/.config/uoft-tools/nautobot.yaml`
    - `~/.config/uoft-tools/nautobot.json`
    - `~/.config/uoft-tools/nautobot.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/nautobot.ini`
    - `~/Library/Preferences/uoft-tools/nautobot.yaml`
    - `~/Library/Preferences/uoft-tools/nautobot.json`
    - `~/Library/Preferences/uoft-tools/nautobot.toml`


    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `NAUTOBOT_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `NAUTOBOT_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-nautobot` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.

3. Environment variables. Environment variables are loaded from the `NAUTOBOT_` namespace. For example, the `foo` configuration option can be set by setting the `NAUTOBOT_FOO` environment variable.

Configuration Options:
<!--
[[[cog 
import tasks.codegen as c; c.gen_conf_table('uoft_nautobot')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| debug | bool |  |  |  |
| allowed_hosts | str |  |  |  |
| secret_key | SecretStr |  |  |  |
| db_host | str |  |  | localhost |
| db_port | int |  |  | 5432 |
| db_name | str |  |  | nautobot |
| db_user | str |  |  | nautobot |
| db_password | SecretStr |  |  |  |
| db_timeout | int |  |  | 300 |
| redis_host | str |  |  | localhost |
| redis_port | int |  |  | 6379 |
| redis_username | str |  |  |  |
| redis_password | SecretStr |  |  |  |
| redis_ssl | bool |  |  |  |
| bluecat_url | str |  |  | https://localhost |
| bluecat_username | str |  |  | admin |
| bluecat_password | SecretStr |  |  |  |
| nornir_username | str |  |  |  |
| nornir_password | SecretStr |  |  |  |
| nornir_secret | SecretStr |  |  |  |
| nornir_timeout | int |  |  | 30 |
| gitlab_username | str |  |  |  |
| gitlab_password | SecretStr |  |  |  |
| ldap_server | str |  |  |  |
| ldap_is_active_directory | bool |  |  |  |
| ldap_cert_is_self_signed | bool |  |  |  |
| ldap_bind_dn | str |  |  |  |
| ldap_bind_password | SecretStr |  |  |  |
| ldap_user_search_base | str |  |  | OU=UTORIDStaff,OU=Staff Users,DC=utscad,DC=utsc,DC=utoronto,DC=ca |
| ldap_user_attribute_map | str |  |  |  |
| ldap_group_search_base | str |  |  | OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca |
| ldap_groups_active | str |  |  | GL_IITS_Users |
| ldap_groups_staff | str |  |  | GL_SysNetAdmins |
| ldap_groups_superuser | str |  |  | GL_SysNet_SuperUsers |
| ldap_additional_groups | str |  |  |  |
| aruba | Settings |  |  | svc_account='apiadmin' mm_vrrp_hostname='sdc-aruba-mobility-conductor-5k-01.netmgmt.utsc.utoronto.ca' md_hostnames=['aruba-7240xm-01.netmgmt.utsc.utoronto.ca', 'aruba-7240xm-02.netmgmt.utsc.utoronto.ca'] password=SecretStr('**********') default_config_path='/md/UTSC' |
<!--[[[end]]] -->

## License

MIT