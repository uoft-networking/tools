import subprocess

import pynautobot
import requests

token = (
    subprocess.run(
        ["pass", "show", "nautobot-api-token"], capture_output=True, text=True
    )
    .stdout.strip()
    .splitlines()[-1]
)

url = "https://dev.engine.netmgmt.utsc.utoronto.ca/"

try:
    response = requests.get(url)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print('need to run `./run nautobot. start` to start the nautobot server')
    exit(1)

nautobot = pynautobot.api(url, token=token)

print()