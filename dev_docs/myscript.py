import requests
from requests.auth import HTTPBasicAuth

host = "example-server.utoronto.ca"
username = "myusername"
password = "mypassword"

response = requests.get(
    f"http://{host}/anything",
    json={"the-data-i-want": ["result one", "result two", "result three"]},
    auth=HTTPBasicAuth(username, password)
)
mydata = response.json()['json']["the-data-i-want"]

print(mydata)
