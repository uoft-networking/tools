"""
To rebuild the _vendor package:
touch __init__.py
pip install --no-deps -t . ruamel.yaml tomlkit
mv ruamel.yaml-*.dist-info/LICENSE ruamel/yaml
mv tomlkit-*.dist-info/LICENSE tomlkit/
mv ruamel/yaml ./
mv tomlkit toml
rm -rf ruamel*
rm -rf *.dist-info
"""
