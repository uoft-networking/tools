# uoft_phpipam

A collection of tool to interact with a phpIPAM instance.

## Usage

ansible-lookup      -  From a serial, returns a dictionary configuration object to be used in Ansible.
```console
uoft phpipam ansible-lookup 1234567890
```

serial-lookup      -  From a serial, returns a dictionary object of a given device.
```console
uoft phpipam serial-lookup 1234567890
```

## Installation

See OS specific installation instructions below.

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_phpipam
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
    - `/etc/xdg/uoft-tools/phpipam.ini`
    - `/etc/xdg/uoft-tools/phpipam.yaml`
    - `/etc/xdg/uoft-tools/phpipam.json`
    - `/etc/xdg/uoft-tools/phpipam.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/phpipam.ini`
    - `~/.config/uoft-tools/phpipam.yaml`
    - `~/.config/uoft-tools/phpipam.json`
    - `~/.config/uoft-tools/phpipam.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/phpipam.ini`
    - `/Library/Preferences/uoft-tools/phpipam.yaml`
    - `/Library/Preferences/uoft-tools/phpipam.json`
    - `/Library/Preferences/uoft-tools/phpipam.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/phpipam.ini`
    - `~/.config/uoft-tools/phpipam.yaml`
    - `~/.config/uoft-tools/phpipam.json`
    - `~/.config/uoft-tools/phpipam.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/phpipam.ini`
    - `~/Library/Preferences/uoft-tools/phpipam.yaml`
    - `~/Library/Preferences/uoft-tools/phpipam.json`
    - `~/Library/Preferences/uoft-tools/phpipam.toml`


    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `PHPIPAM_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `PHPIPAM_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-phpipam` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.
Do not supply a password for this password store if you intend to use these tools in an automated fashion, or you will have to authenticate often.
    ```console
    gpg --quick-generate-key <STORE_NAME>
    pass init <STORE_NAME>
    pass edit example-password
    ```
    ```console
    username = "your-name"
    password = "secure-password"
    ```

3. Environment variables. Environment variables are loaded from the `PHPIPAM_` namespace. For example, the `foo` configuration option can be set by setting the `PHPIPAM_FOO` environment variable.

<!--
[[[cog 
import tasks.codegen as c; c.gen_conf_table('uoft_phpipam')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| hostname | str |  | Hostname of phpIPAM instance. |  |
| username | str |  | Username for phpIPAM instance. |  |
| password | SecretStr |  | Password for phpIPAM instance. |  |
| app_id | str |  | App id for API access. |  |
<!--[[[end]]] -->

## License

MIT