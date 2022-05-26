from requests import Session
import requests.packages


class ArubaRESTAPIClient:
    def __init__(self, host, username, password) -> None:
        self.host = host
        self.v1_url = f"https://{self.host}/v1/"
        self.rest_v1_url = f"https://{self.host}/rest/v1/"
        self.auth = dict(username=username, password=password)
        self.session = Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )
        self.session.params.update({"json": 1, "config_path": "/mm"})  # type: ignore

        # pylint: disable=no-member
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)  # type: ignore
        self.session.verify = False

        self.login()

    def login(self):
        r = self.session.post(self.v1_url + "api/login", data=self.auth)
        assert r.status_code == 200, f"Auth failed on host {self.host}: {r.text}"
        token = r.json()["_global_result"]["UIDARUBA"]
        self.session.cookies["SESSION"] = token
        self.session.headers.update({"SESSION": token, "uidaruba": token})
        self.session.params.update({"UIDARUBA": token})  # type: ignore

    def logout(self):
        self.session.delete(self.rest_v1_url + "login-sessions")

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        self.logout()

    def showcommand(self, cmd, **params):
        return self.session.get(
            self.v1_url + "configuration/showcommand",
            params=dict(command=cmd, **params),
        ).json()

    def get_all_objects(self):
        return self.session.get(
            self.v1_url + "configuration/object",
        ).json()

    def get_all_containers(self):
        return self.session.get(
            self.v1_url + "configuration/container",
        ).json()

    def stm_blacklist_get(self):
        return self.showcommand("show ap blacklist-clients")

    def stm_blacklist_remove(self, mac_address):
        resp = self.session.post(
            self.v1_url + "configuration/object/stm_blacklist_client_remove",
            json={"client-mac": mac_address},
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.host} failed: {resp.text}"
        resp_data = resp.json()
        # API reports success, wether mac address existed in blacklist or not
        assert (
            resp_data["_global_result"]["status_str"] == "Success"
        ), f"API Request to host {self.host} did not succeed: {resp_data}"
