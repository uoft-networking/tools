import os
from invoke import task, Context

from tasks.common import needs_sudo


PROD_SERVICES = ["nautobot", "nautobot-scheduler", "nautobot-worker"]
DEV_SERVICES = ["nautobot-dev", "nautobot-dev-scheduler", "nautobot-dev-worker"]


@task()
def server(c: Context, cmdline: str):
    with c.cd("projects/nautobot"):
        c.run(f"direnv exec . nautobot-server {cmdline}")


@task()
def start(c: Context):
    server(c, "runserver --noreload")


@task(
    help={
        "action": "any valid systemd action, or the special actions 'edit' and 'tail'"
    }
)
def systemd(c: Context, action: str, prod: bool = False):
    """
    Run systemd commands on the services
    """

    services = PROD_SERVICES if prod else DEV_SERVICES
    if action == "edit":
        services = " ".join([f"/etc/systemd/system/{s}.service" for s in services])
        c.run(f"sudoedit {services}")
    elif action == "tail":
        services = " ".join([f"-u {s}" for s in services])
        c.run(f"sudo journalctl -f {services}")
    else:
        c.run(f"sudo systemctl {action} {' '.join(services)}")


@task()
def prod_shell(c: Context):
    needs_sudo(c)
    c.sudo("env -C /opt/nautobot bash --login", pty=True, user='nautobot')


def _parse_built_files(output: str) -> tuple[str, str]:
    _, _, r = output.partition("Successfully built ")
    sdist, _, wheel = r.partition(" and ")
    wheel = wheel.splitlines()[0].strip()
    return sdist, wheel


@task()
def deploy_to_prod(c: Context):
    r = c.run("inv build core")
    _, core_wheel = _parse_built_files(r.stdout)
    r = c.run("inv build nautobot")
    _, nautobot_wheel = _parse_built_files(r.stdout)
    systemd(c, "stop", prod=True)
    wheels = f"dist/{core_wheel} dist/{nautobot_wheel}"
    needs_sudo(c)
    c.sudo(f"gpipx runpip nautobot install --upgrade {wheels}")
    c.sudo(
        f"gpipx runpip nautobot install --upgrade --force-reinstall --no-deps {wheels}"
    )
    c.sudo(
        "cp projects/nautobot/dev_data/nautobot_config.py /opt/nautobot/nautobot_config.py"
    )
    c.sudo("chown nautobot:nautobot /opt/nautobot/nautobot_config.py")
    c.sudo("chmod 644 /opt/nautobot/nautobot_config.py")
    c.run("sudo -iu nautobot direnv exec /opt/nautobot nautobot-server migrate")
    systemd(c, "start", prod=True)
    systemd(c, "status", prod=True)


@task()
def db_refresh(c: Context):
    systemd(c, "stop")
    c.run("/opt/backups/db/actions sync_prod_to_dev")
    c.run("inv nautobot.server migrate")
    systemd(c, "start")


@task()
def curl_as(c: Context, endpoint: str, user: str = "me", prod: bool = False, method="GET"):
    if user == "me":
        token = os.environ["MY_API_TOKEN"]
    else:
        token = os.environ["HELPDESK_API_TOKEN"]
    if prod:
        url = "https://engine.netmgmt.utsc.utoronto.ca/api"
    else:
        url = "https://dev.engine.netmgmt.utsc.utoronto.ca/api"
    c.run(
        f"curl -H 'Authorization: Token {token}' -H 'Accept: application/json;' -H 'Content-Type: application/json' -X {method} {url}/{endpoint}"
    )
