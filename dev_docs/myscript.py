from argparse import ArgumentParser
from configparser import ConfigParser

import requests
from requests.auth import HTTPBasicAuth

parser = ArgumentParser()
parser.add_argument("--host", default=None, help="The host to connect to")
parser.add_argument("--username", default=None, help="The username for the user")
parser.add_argument("--password", default=None, help="The password for the user")
args = parser.parse_args()

config = ConfigParser()
config.read("config.ini")
host = config["DEFAULT"]["host"]
username = config["DEFAULT"]["username"]
password = config["DEFAULT"]["password"]

host = args.host if args.host else host
username = args.username if args.username else username
password = args.password if args.password else password

response = requests.get(
    f"https://{host}/api/v1/data", auth=HTTPBasicAuth(username, password)
)
mydata = response.json()["the-data-i-want"]

print(mydata)
