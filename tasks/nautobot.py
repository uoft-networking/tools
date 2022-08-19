import os
from invoke import task, call, Context


PROD_SERVICES = ["nautobot", "nautobot-scheduler", "nautobot-worker"]
DEV_SERVICES = ["nautobot-dev", "nautobot-dev-scheduler", "nautobot-dev-worker"]


@task()
def start(ctx: Context):
    with ctx.cd("projects/nautobot"):
        ctx.run("direnv exec . nautobot-server runserver --noreload")


@task(
    help={
        "action": "any valid systemd action, or the special actions 'edit' and 'tail'"
    }
)
def systemd(ctx: Context, action: str, prod: bool = False):
    """
    Run systemd commands on the services
    """

    services = PROD_SERVICES if prod else DEV_SERVICES
    if action == "edit":
        services = " ".join([f"/etc/systemd/system/{s}.service" for s in services])
        ctx.run(f"sudoedit {services}")
    elif action == "tail":
        services = " ".join([f"-u {s}" for s in services])
        ctx.run(f"sudo journalctl -f {services}")
    else:
        ctx.run(f"sudo systemctl {action} {' '.join(services)}")


@task()
def prod_shell(ctx: Context):
    ctx.run("sudo -u nautobot env -C /opt/nautobot bash --login", pty=True)


def _parse_built_files(output: str) -> tuple[str, str]:
    _, _, r = output.partition("Successfully built ")
    sdist, _, wheel = r.partition(" and ")
    wheel = wheel.splitlines()[0].strip()
    return sdist, wheel


@task()
def deploy_to_prod(ctx: Context):
    r = ctx.run("inv build core")
    _, core_wheel = _parse_built_files(r.stdout)
    r = ctx.run("inv build nautobot")
    _, nautobot_wheel = _parse_built_files(r.stdout)
    ctx.run("inv nautobot.systemd --prod stop")
    wheels = f"dist/{core_wheel} dist/{nautobot_wheel}"
    ctx.run(f"gpipx runpip nautobot install --upgrade {wheels}")
    ctx.run(
        f"gpipx runpip nautobot install --upgrade --force-reinstall --no-deps {wheels}"
    )
    ctx.run(
        "sudo cp projects/nautobot/dev_data/nautobot_config.py /opt/nautobot/nautobot_config.py"
    )
    ctx.run("sudo chown nautobot:nautobot /opt/nautobot/nautobot_config.py")
    ctx.run("sudo chmod 644 /opt/nautobot/nautobot_config.py")
    ctx.run("sudo -iu nautobot direnv exec /opt/nautobot nautobot-server migrate")
    ctx.run("inv nautobot.systemd --prod start")
    ctx.run("inv nautobot.systemd --prod status")


@task(pre=[call(systemd, "stop")], post=[call(systemd, "start")])
def db_refresh(ctx: Context):
    ctx.run("/opt/backups/db/actions sync_prod_to_dev")
    with ctx.cd("projects/nautobot"):
        ctx.run("nautobot-server migrate")


@task()
def curl_as(ctx: Context, endpoint: str, user: str = "me", prod: bool = False, method="GET"):
    if user == "me":
        token = os.environ["MY_API_TOKEN"]
    else:
        token = os.environ["HELPDESK_API_TOKEN"]
    if prod:
        url = "https://engine.netmgmt.utsc.utoronto.ca/api"
    else:
        url = "https://dev.engine.netmgmt.utsc.utoronto.ca/api"
    ctx.run(
        f"curl -H 'Authorization: Token {token}' -H 'Accept: application/json;' -H 'Content-Type: application/json' -X {method} {url}/{endpoint}"
    )
