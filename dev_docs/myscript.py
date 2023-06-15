import requests
from requests.auth import HTTPBasicAuth

host = "example-server.utoronto.ca"
username = "myusername"
password = "mypassword"

response = requests.get(
    f"https://{host}/api/v1/data", 
    auth=HTTPBasicAuth(username, password)
)
mydata = response.json()["the-data-i-want"]

print(mydata)
