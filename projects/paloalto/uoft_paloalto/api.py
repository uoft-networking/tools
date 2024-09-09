from uoft_core.api import APIBase


class API(APIBase):
    def __init__(self, base_url: str, username: str, password: str):
        super().__init__(base_url, api_root="/restapi/v10.2")
        self.username = username
        self.password = password
        self.verify = False

    def login(self):
        # PA NSM supports basic authentication, so the login process is actually quite simple
        self.auth = (self.username, self.password)
