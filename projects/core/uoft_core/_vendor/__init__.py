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
grep -rl 'if False:' yaml | xargs sed -i '' 's/if False:/from typing import TYPE_CHECKING\nif TYPE_CHECKING:/g'
grep -rl 'from ruamel.yaml.' yaml | xargs sed -i '' 's/from ruamel.yaml./from ./g'
grep -rl 'import ruamel.yaml' yaml | xargs sed -i '' 's/import ruamel.yaml//g'
"""
