from jinja2.ext import Extension
import subprocess

class Git():

    def _get(self, val):
        try:
            return subprocess.check_output(["git", "config", "--get", val]).strip().decode("utf-8")
        except subprocess.CalledProcessError:
            return None

    @property
    def username(self):
        return self._get("user.name")

    @property
    def email(self):
        return self._get("user.email")

class DefaultsFromGit(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.globals["git"] = Git()
