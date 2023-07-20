from requests import Session
import urllib3


class ArubaRESTAPIError(Exception):
    pass


class ArubaRESTAPIClient:
    def __init__(self, host, username, password, default_config_path = "/mm", ssl_verify = False) -> None:
        self.host = host
        self.auth = dict(username=username, password=password)
        self.session = Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

        self.default_config_path = default_config_path

        # pylint: disable=no-member
        # Aruba controller's cert is self-signed, and cannot be verified
        if not ssl_verify:
            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore

    def login(self):
        r = self.session.post(self.endpoint.login, data=self.auth)

        if r.status_code != 200:
            raise ArubaRESTAPIError(f"Login failed on host {self.host}: {r.text}")

        res = r.json()["_global_result"]
        token = res["UIDARUBA"]
        csrf_token = res["X-CSRF-Token"]

        self.session.cookies["SESSION"] = token
        self.session.headers.update(
            {"SESSION": token, "uidaruba": token, "X-CSRF-Token": csrf_token}
        )
        self.session.params.update({"UIDARUBA": token, "config_path": self.default_config_path})  # type: ignore

    def logout(self):
        self.session.delete(self.endpoint.logout)

    def show_raw(self, cmd, **params):
        return self.session.get(
            self.endpoint.showcommand,
            params=dict(command=cmd, json=1, **params),
        )

    def showcommand(self, cmd: str, **params):
        return self.show_raw(cmd, **params).json()

    def post(self, object_name: str, data: dict | None = None, **kwargs):
        """
        Make a post request to the API for a given object
        For example, calling this method with object_name="ap" and data={"name": "test-ap"} is equivalent to calling
        self.session.post("https://<host>/v1/configuration/object/ap", data={"name": "test-ap"})
        """
        url = f"{self.endpoint.object}/{object_name}"
        resp = self.session.post(url, json=data, **kwargs)

        if resp.status_code != 200:
            raise ArubaRESTAPIError(f"POST {url} failed: {resp.text}")

        resp_data = resp.json()

        if "Error" in resp_data:
            raise ArubaRESTAPIError(f"POST {url} failed: {resp_data}")

        if resp_data["_global_result"]["status_str"] != "Success":
            raise ArubaRESTAPIError(f"POST {url} failed: {resp_data}")

        return resp_data

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, type_, value, traceback):
        self.logout()

    @property
    def endpoint(self):
        "container for all API endpoint URLs"

        class Endpoint:
            # This class is a pure namespace, as opposed to a standard instantiable python class with an init function
            # Since the namespace class acts as a container for methods, the `self` variable is nonlocal, and refers to
            # the namespace's parent class, which is the ArubaRESTAPIClient class
            nonlocal self
            login = f"https://{self.host}/v1/api/login"
            logout = f"https://{self.host}/rest/v1/login-sessions"
            showcommand = f"https://{self.host}/v1/configuration/showcommand"
            object = f"https://{self.host}/v1/configuration/object"
            container = f"https://{self.host}/v1/configuration/container"
            xml = f"https://{self.host}/screens/cmnutil/execUiQuery.xml"

        return Endpoint

    @property
    def get(self):
        "container for all uncategorized get requests"

        class Get:
            # This class is a pure namespace, as opposed to a standard instantiable python class with an init function
            # Since the namespace class acts as a container for methods, the `self` variable is nonlocal, and refers to
            # the namespace's parent class, which is the ArubaRESTAPIClient class
            nonlocal self

            @staticmethod
            def user_table():
                return self.showcommand("show user-table")["Users"]

            @staticmethod
            def ap_database():
                return self.showcommand("show ap database")["AP Database"]

            @staticmethod
            def ap_active():
                return self.showcommand("show ap active")["Active AP Table"]

            @staticmethod
            def ap_radio_summary():
                return self.showcommand("show ap radio-summary")[
                    "APs Radios information"
                ]

            @staticmethod
            def all_objects():
                return self.session.get(self.endpoint.object).json()

            @staticmethod
            def all_containers():
                return self.session.get(self.endpoint.container).json()

        return Get

    @property
    def ap_provisioning(self):
        "method container for all AP provisioning operations"

        class AP_Provisioning:
            # This class is a pure namespace, as opposed to a standard instantiable python class with an init function
            # Since the namespace class acts as a container for methods, the `self` variable is nonlocal, and refers to
            # the namespace's parent class, which is the ArubaRESTAPIClient class
            nonlocal self

            @staticmethod
            def wdb_cpsec_add_mac(mac_address: str, ap_group: str, ap_name: str):
                return self.post(
                    "wdb_cpsec_add_mac",
                    data={
                        "name": mac_address,
                        "ap_group": ap_group,
                        "ap_name": ap_name
                    },
                )

            @staticmethod
            def wdb_cpsec_modify_mac_factory_approved(mac_address: str):
                return self.post(
                    "wdb_cpsec_modify_mac",
                    {
                        "name": mac_address,
                        "certtype": "factory-cert",
                        "act": "certified-factory-cert",
                    },
                )

            @staticmethod
            def wdb_cpsec_delete_mac(mac_address):
                return self.post(
                    "wdb_cpsec_del_mac",
                    {"name": mac_address},
                )

            @staticmethod
            def wdb_cpsec_revoke_mac(mac_address, revoke_text):
                return self.post(
                    "/wdb_cpsec_revoke_mac",
                    {"name": mac_address, "revoke-text": revoke_text},
                )

            @staticmethod
            def get_cpsec_whitelist():
                return self.showcommand("show whitelist-db cpsec")['Control-Plane Security Allowlist-entry Details']

        return AP_Provisioning

    @property
    def controller(self):
        "method container for all controller operations"

        class Controller:
            # This class is a pure namespace, as opposed to a standard instantiable python class with an init function
            # Since the namespace class acts as a container for methods, the `self` variable is nonlocal, and refers to
            # the namespace's parent class, which is the ArubaRESTAPIClient class
            nonlocal self

            @staticmethod
            def write_memory():
                return self.post("write_memory")

        return Controller

    @property
    def wlan(self):
        "method container for all WLAN operations"

        class WLAN:
            # This class is a pure namespace, as opposed to a standard instantiable python class with an init function
            # Since the namespace class acts as a container for methods, the `self` variable is nonlocal, and refers to
            # the namespace's parent class, which is the ArubaRESTAPIClient class
            nonlocal self

            @staticmethod
            def get_ap_groups():
                res = self.session.get(
                    self.endpoint.object + "/ap_group"
                ).json()
                return res["_data"]["ap_group"]

            @staticmethod
            def get_ap_client_blacklist():
                res = self.showcommand("show ap blacklist-clients")
                # In AOS 8.10, the output key was changed from "Blacklisted Clients" to "Client Denylist"
                return res.get("Blacklisted Clients", res.get("Client Denylist"))

            @staticmethod
            def stm_blacklist_remove(mac_address: str):
                return self.post(
                    "stm_blacklist_client_remove", {"client-mac": mac_address}
                )

            @staticmethod
            def blmgr_blacklist_add(mac_address: str):
                return self.post(
                    "blmgr_blacklist_client_add", {"client-mac": mac_address}
                )

            @staticmethod
            def blmgr_blacklist_remove(mac_address: str):
                return self.post(
                    "blmgr_blacklist_client_remove", {"client-mac": mac_address}
                )

            @staticmethod
            def blmgr_blacklist_purge():
                return self.post("blmgr_blacklist_clients_purge", {})

        return WLAN
