#!/usr/bin/env bash
"exec" "-a" "$0" "$(dirname $(realpath $0))/python3.10" "$0" "$@"

from pathlib import Path
from subprocess import run

here = Path(__file__).parent

for file in here.iterdir():
    ftype = run(["file", str(file)], check=True, capture_output=True).stdout.decode().strip()
    if 'text executable' not in ftype:
        continue
    contents = file.read_text().splitlines()
    if'python3' in contents[0] and str(here) not in contents[0]:
        print(f"Fixing shebang for {file}")
        contents[0] = "#!/usr/bin/env bash"
        contents.insert(1, '"exec" "-a" "$0" "$(dirname $(realpath $0))/python3.10" "$0" "$@"')
        file.write_text("\n".join(contents))
