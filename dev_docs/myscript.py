from argparse import ArgumentParser

import requests
from requests.auth import HTTPBasicAuth

parser = ArgumentParser()
parser.add_argument("host", help="The host to connect to")
parser.add_argument("username", help="The username for the user")
parser.add_argument("password", help="The password for the user")
args = parser.parse_args()

host = args.host
username = args.username
password = args.password

response = requests.get(
    f"https://{host}/api/v1/data",
    auth=HTTPBasicAuth(username, password)
)
mydata = response.json()["the-data-i-want"]

print(mydata)
