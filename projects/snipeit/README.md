# uoft snipeit

Collection of tools to interact with SnipeIT, currently focused around Access Point provisioning, but will probably be expanded to support all asset types in general.

## Usage

create-asset      -  Create an asset.
```console
uoft snipeit create-asset 12:12:12:12:12:12 Testname 1234567890
```
Currently the create-asset command defaults to the 'model-id' for an Aruba AP 535.  To override this please supply the '--model-id' option followed by the INTEGER model-id as known in SnipeIT.
```console
uoft snipeit create-asset --model-id 120 12:12:12:12:12:12 Testname 1234567890
```

checkout-asset    -  Checkout an asset.
```console
uoft snipeit checkout-asset 02616
```
You will then be prompted, interactively, to select from a list of all locations available on your SnipeIT system.
Optionally, you can override then and provide the INTEGER location-id as known in SnipeIT
```console
uoft snipeit checkout-asset --location-id 150 02616
```

generate-label    -  Generate an asset label.
```console
uoft snipeit generate-label 02197
```
This will generate and save 'Asset-Label.jpg' in your $HOME directory.

print-label       -  Print the last generated label.
```console
uoft snipeit print-label
```
This will print 'Asset-Label.jpg' in your $HOME directory.  NOTE: This program assumes you are using a brother QL-800 printer with 29x90mm die-cut labels.

Collection of tools to interact with SnipeIT, currently focused around Access Point provisioning, but will probably be expanded to support all asset types in general.
single-provision  -  Single provision from INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for the given asset provided.
```console
uoft snipeit single-provision 12:12:12:12:12:12 Testname 1234567890
```
You will then be prompted, interactively, to select from a list of all locations available on your SnipeIT system.
Optionally, you can override then and provide the INTEGER location-id as known in SnipeIT
```console
uoft snipeit single-provision --location-id 150 12:12:12:12:12:12 Testname 1234567890
```
Note: Currently the batch-provision command defaults to the 'model-id' for an Aruba AP 535.  To override this please supply the '--model-id' option followed by the INTEGER model-id as known in SnipeIT.
```console
uoft snipeit single-provision --location-id 150 12:12:12:12:12:12 --model-id 100 Testname 1234567890
```

batch-provision   -  Batch provisioning from FILE and INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for each given asset name. Names are taken from file/interactive input, and Mac's/Serials are taken from interactive input, in pairs of two, typically scanned via barcode scanner.
```console
uoft snipeit batch-provision (<NAMES_LIST_FILE> OR <->)
```
You will then be prompted to supply the mac-address and serial for each of the given ap-names from your input.  As you submit each pair a label will be printed as well before you are prompted for the next pair.  It is recommended to do this operation in smaller batches of five to ten at once, but not necessary. A list of provisioned mac-addresses will be returned to you on completion for use in further provisioning.
Note: Currently the batch-provision command defaults to the 'model-id' for an Aruba AP 535.  To override this please supply the '--model-id' option followed by the INTEGER model-id as known in SnipeIT.

## Installation

See OS specific installation instructions below.

### Requirements

This software requires Python3.10 or higher.
We recommend you install this software with [pipx](https://pypa.github.io/pipx/):

### MacOS / Linux

```console
$ python3.10 -m pip install --user pipx
$ pipx install uoft_snipeit
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
    - `/etc/xdg/uoft-tools/snipeit.ini`
    - `/etc/xdg/uoft-tools/snipeit.yaml`
    - `/etc/xdg/uoft-tools/snipeit.json`
    - `/etc/xdg/uoft-tools/snipeit.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/snipeit.ini`
    - `~/.config/uoft-tools/snipeit.yaml`
    - `~/.config/uoft-tools/snipeit.json`
    - `~/.config/uoft-tools/snipeit.toml`

    MacOS:
    - `/Library/Preferences/uoft-tools/shared.ini`
    - `/Library/Preferences/uoft-tools/shared.yaml`
    - `/Library/Preferences/uoft-tools/shared.json`
    - `/Library/Preferences/uoft-tools/shared.toml`
    - `/Library/Preferences/uoft-tools/snipeit.ini`
    - `/Library/Preferences/uoft-tools/snipeit.yaml`
    - `/Library/Preferences/uoft-tools/snipeit.json`
    - `/Library/Preferences/uoft-tools/snipeit.toml`
    - `~/.config/uoft-tools/shared.ini`
    - `~/.config/uoft-tools/shared.yaml`
    - `~/.config/uoft-tools/shared.json`
    - `~/.config/uoft-tools/shared.toml`
    - `~/.config/uoft-tools/snipeit.ini`
    - `~/.config/uoft-tools/snipeit.yaml`
    - `~/.config/uoft-tools/snipeit.json`
    - `~/.config/uoft-tools/snipeit.toml`
    - `~/Library/Preferences/uoft-tools/shared.ini`
    - `~/Library/Preferences/uoft-tools/shared.yaml`
    - `~/Library/Preferences/uoft-tools/shared.json`
    - `~/Library/Preferences/uoft-tools/shared.toml`
    - `~/Library/Preferences/uoft-tools/snipeit.ini`
    - `~/Library/Preferences/uoft-tools/snipeit.yaml`
    - `~/Library/Preferences/uoft-tools/snipeit.json`
    - `~/Library/Preferences/uoft-tools/snipeit.toml`

    The site-wide config directory (`/etc/xdg/uoft-tools` or `/Library/Preferences` in the above example) can be overridden by setting the `SNIPEIT_SITE_CONFIG` environment variable.

    The user config directory (`~/.config/uoft-tools` or `~/Library/Preferences` in the above example) can be overridden by setting the `SNIPEIT_USER_CONFIG` environment variable.

2. [Pass](https://www.passwordstore.org/) secret named `uoft-snipeit` (if available). Configuration stored in pass must be written in [TOML](https://toml.io/en/) format.
    Do not supply a password for this password store if you intend to use these tools in an automated fashion, or you will have to authenticate often.
    ```console
    gpg --quick-generate-key <STORE_NAME>
    pass init <STORE_NAME>
    pass edit example-password
    ```
    ```console
    api_bearer_key = "q1w2e3r4t5y6u7i8o9p0"
    snipeit_hostname = "example.com"
    ```

3. Environment variables. Environment variables are loaded from the `SNIPEIT_` namespace. For example, the `foo` configuration option can be set by setting the `SNIPEIT_FOO` environment variable.

Configuration Options:
<!--
[[[cog 
import tasks.codegen as c; c.gen_conf_table('uoft_snipeit')
]]] -->
| Option | Type | Title | Description | Default |
| ------ | ---- | ----- | ----------- | ------- |
| api_bearer_key | SecretStr |  | User API bearer key used with SnipeIT instance. |  |
| snipeit_hostname | str |  | Hostname of SnipeIT instance. |  |
<!--[[[end]]] -->

## License

MIT