from requests import Session
from . import Settings


class phpIPAMRESTAPIClient:
    def __init__(self, hostname: str, username: str, password: str, app_id) -> None:
        self.hostname = hostname
        self.password = password
        self.username = username
        self.app_id = app_id
        self.rest_url = f"https://{self.hostname}/api/{self.app_id}/"
        self.auth = dict(username=username, password=password)
        self.session = Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def login(self):
        r = self.session.post(self.rest_url + "user", auth=(self.username, self.password))
        assert r.status_code == 200, f"Auth failed on host {self.hostname}: {r.text}"
        token = r.json()["data"]["token"]
        self.session.cookies["SESSION"] = token
        self.session.headers.update({"SESSION": token, "phpipam-token": token})

    def logout(self):
        self.session.delete(self.rest_url + "user/")

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, type_, value, traceback):
        self.logout()

    def get_sections_raw(self):
        return self.session.get(self.rest_url + "sections/")

    def mac_search_raw(self, mac_address):
        return self.session.get(self.rest_url + f"addresses/search_mac/{mac_address}/")

    def subnet_search_raw(self, subnet_id):
        return self.session.get(self.rest_url + f"subnets/{subnet_id}/")

    def vlan_search_raw(self, vlan_id):
        return self.session.get(self.rest_url + f"vlan/{vlan_id}/")

    def get_all_addresses_raw(self):
        return self.session.get(self.rest_url + f"addresses/all/")

    def get_location_raw(self, location_id):
        return self.session.get(self.rest_url + f"tools/locations/{location_id}/")

    @classmethod
    def from_settings(cls, settings: Settings) -> "phpIPAMRESTAPIClient":
        return cls(settings.phpipam_hostname, settings.username, settings.password.get_secret_value(), settings.app_id)
