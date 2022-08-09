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

        self.ap_provisioning = AP_Provisioning(self)
        self.controller = Controller(self)
        self.wlan = WLAN(self)

    def login(self):
        r = self.session.post(self.v1_url + "api/login", data=self.auth)
        assert r.status_code == 200, f"Auth failed on host {self.host}: {r.text}"
        token = r.json()["_global_result"]["UIDARUBA"]
        self.session.cookies["SESSION"] = token
        self.session.headers.update({"SESSION": token, "uidaruba": token})
        self.session.params.update({"UIDARUBA": token})  # type: ignore

    def logout(self):
        self.session.delete(self.rest_v1_url + "login-sessions")

    def show_raw(self, cmd, **params):
        return self.session.get(
            self.v1_url + "configuration/showcommand",
            params=dict(command=cmd, **params),
        )

    def showcommand(self, cmd, **params):
        return self.show_raw(cmd, **params).json()

    def stm_blacklist_get(self):
        return self.showcommand("show ap blacklist-clients")["Blacklisted Clients"]

    def stm_blacklist_remove(self, mac_address: str):
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

    def get_user_table(self):
        return self.showcommand("show user-table")["Users"]

    def get_ap_database(self):
        return self.showcommand("show ap database")["AP Database"]

    def get_ap_active(self):
        return self.showcommand("show ap active")["Active AP Table"]

    def get_ap_radio_summary(self):
        return self.showcommand("show ap radio-summary")["APs Radios information"]

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, type_, value, traceback):
        self.logout()

    def get_all_objects(self):
        return self.session.get(
            self.v1_url + "configuration/object",
        ).json()

    def get_all_containers(self):
        return self.session.get(
            self.v1_url + "configuration/container",
        ).json()


class AP_Provisioning:
    def __init__(self, parent: "ArubaRESTAPIClient"):
        self.parent = parent

    def wdb_cpsec_add_mac(self, mac_address, ap_group, ap_name):
        resp = self.parent.session.post(
            self.parent.v1_url + "configuration/object/wdb_cpsec_add_mac",
            json={"name": mac_address, "ap_group": ap_group, "ap_name": ap_name},
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.parent.host} failed: {resp.text}"

    def wdb_cpsec_modify_mac_factory_approved(self, mac_address):
        resp = self.parent.session.post(
            self.parent.v1_url + "configuration/object/wdb_cpsec_modify_mac",
            json={
                "name": mac_address,
                "certtype": "factory-cert",
                "act": "approved-ready-for-cert",
            },
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.parent.host} failed: {resp.text}"

    def wdb_cpsec_delete_mac(self, mac_address):
        resp = self.parent.session.post(
            self.parent.v1_url + "configuration/object/wdb_cpsec_add_mac",
            json={"name": mac_address},
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.parent.host} failed: {resp.text}"

    def wdb_cpsec_revoke_mac(self, mac_address, revoke_text):
        resp = self.parent.session.post(
            self.parent.v1_url + "configuration/object/wdb_cpsec_add_mac",
            json={"name": mac_address, "revoke-text": revoke_text},
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.parent.host} failed: {resp.text}"


class Controller:
    def __init__(self, parent: "ArubaRESTAPIClient"):
        self.parent = parent

    def write_memory(self):
        resp = self.parent.session.post(
            self.parent.v1_url + "configuration/object/write_memory",
        )
        assert (
            resp.status_code == 200
        ), f"API Request to host {self.parent.host} failed: {resp.text}"


class WLAN:
    def __init__(self, parent: "ArubaRESTAPIClient"):
        self.parent = parent

    def get_ap_groups(self):
        return self.parent.session.get(
            self.parent.v1_url + "configuration/object/ap_group",
            ).json()
