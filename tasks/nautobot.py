"nautobot-specific tasks"

import os
from typing import Annotated, List
import logging
import time
from subprocess import CalledProcessError
from pathlib import Path

import typer
from task_runner import REPO_ROOT, run, sudo
from . import pipx_install

PROD_SERVICES = ["nautobot", "nautobot-scheduler", "nautobot-worker"]
DEV_SERVICES = ["nautobot-dev", "nautobot-dev-scheduler", "nautobot-dev-worker"]

PROD_API_SESSION = None

logger = logging.getLogger(__name__)


def _get_prod_api_session():
    from requests import Session
    from urllib.parse import urljoin

    global PROD_API_SESSION
    if PROD_API_SESSION:
        return PROD_API_SESSION
    base_url, token = run("pass nautobot-api-token", cap=True).splitlines()

    class NautobotSession(Session):
        def request(self, method, url, *args, **kwargs):
            joined_url = urljoin(base_url, url)
            return super().request(method=method, url=joined_url, *args, **kwargs)

    s = NautobotSession()
    s.headers["Authorization"] = f"Token {token}"
    s.headers["Accept"] = "application/json"
    s.headers["Content-Type"] = "application/json"
    PROD_API_SESSION = s
    return s


def server(args: Annotated[List[str] | None, typer.Argument()] = None):
    """run a given nautobot-server subcommand"""
    if args is None:
        args = []

    os.environ["NAUTOBOT_ROOT"] = str(REPO_ROOT / "projects/nautobot/.dev_data")
    from unittest.mock import patch

    with patch("sys.argv", ["nautobot-server", *args]):
        from nautobot.core.cli import main

        main()


def prod_server(args: list[str]):
    """run a given nautobot-server subcommand against the prod server"""
    sudo(
        f"direnv exec . nautobot-server {' '.join(args)}",
        user="nautobot",
        cwd="/opt/nautobot",
    )


def start(args: Annotated[List[str] | None, typer.Argument()] = None):
    """start nautobot dev server"""
    all_args = ["runserver", "--noreload"]
    if args is not None:
        all_args.extend(args)
    server(all_args)


def worker(args: Annotated[List[str] | None, typer.Argument()] = None):
    """start nautobot dev worker instance"""
    all_args = ["celery", "worker", "--loglevel", "DEBUG"]
    if args is not None:
        all_args.extend(args)
    server(all_args)


def db_command(cmd: str):
    """run a SQL command against the dev db using nautobot-server dbshell"""
    server(["dbshell", "--", f"--command={cmd}"])


def systemd(
    action: Annotated[
        str,
        typer.Argument(help="any valid systemd action, or the special actions 'edit' and 'tail'"),
    ],
    prod: Annotated[
        bool,
        typer.Option(help="Run this systemd task against the production systemd services"),
    ] = False,
):
    """
    Run systemd commands on nautobot services
    """

    services = PROD_SERVICES if prod else DEV_SERVICES
    if action == "edit":
        services = " ".join([f"/etc/systemd/system/{s}.service" for s in services])
        run(f"sudoedit {services}")
    elif action == "tail":
        services = " ".join([f"-u {s}" for s in services])
        sudo(f"journalctl -f {services}")
    else:
        sudo(f"systemctl -n 0 {action} {' '.join(services)}")


def prod_shell():
    """start a shell as the prod app user"""
    sudo("bash", user="nautobot", login=True, cwd="/opt/nautobot")


def prod_nbshell():
    """start a nautobot shell as the prod app user"""
    prod_server(["nbshell", "--bpython"])


def deploy_to_prod():
    """build and deploy the current code to prod"""
    systemd("stop", prod=True)
    pipx_install("nautobot")
    sudo(
        "cp projects/nautobot/.dev_data/nautobot_config.py /opt/nautobot/nautobot_config.py",
    )
    sudo("chown nautobot:nautobot /opt/nautobot/nautobot_config.py")
    sudo("chmod 644 /opt/nautobot/nautobot_config.py")
    prod_server(["post_upgrade"])
    systemd("start", prod=True)
    systemd("status", prod=True)


def prod_update_templates():
    """update the prod templates from the current code"""
    repo_path = "projects/nautobot/uoft_nautobot/tests/fixtures/_private/.gitlab_repo"
    run("git add .", cwd=repo_path)
    run("git commit -m 'update templates'", cwd=repo_path, check=False)
    run("git push", cwd=repo_path)
    s = _get_prod_api_session()
    repos = s.get("api/extras/git-repositories").json()["results"]
    templates_repo = next(r for r in repos if r["name"] == "golden_config_templates")
    logger.info(f"Triggering sync of templates repo: {templates_repo['name']}")
    s.post(f"api/extras/git-repositories/{templates_repo['id']}/sync/")
    while True:
        time.sleep(0.5)
        latest_job = s.get("api/extras/job-results/?limit=1").json()["results"][0]
        if latest_job["name"] != "golden_config_templates":
            logger.info("Waiting for 'golden_config_templates' job to complete")
            continue
        if latest_job["status"]["value"] == "completed":
            logger.info("Job completed")
            break


def db_refresh():
    """refresh the dev db from the prod db"""
    try:
        run("/opt/backups/db/actions sync_prod_to_dev", cap=True)
    except CalledProcessError as e:
        if "is being accessed by other users" in e.stderr:
            print("Dev DB is locked. shut down the dev server and try again")
            exit(1)
    db_command("UPDATE extras_gitrepository SET branch='dev' WHERE name='nautobot_data';")
    server(["post_upgrade"])


def refresh_graphql_schema(repo: str | None = None):
    """
    Rebuild local graphql schema file from running models.
    Should be done after every nautobot update, and every
    time a custom field is created or modified
    """
    if repo:
        repo = Path(repo)
    else:
        repo = REPO_ROOT / "projects/nautobot/uoft_nautobot/tests/fixtures/_private/.gitlab_repo"
    server(
        f"graphql_schema --out {repo}/graphql/_schema.graphql".split()  # type: ignore
    )


def curl_as(endpoint: str, user: str = "me", prod: bool = False, method="GET"):
    """curl an endpoint as either myself, or another nautobot user, for testing"""
    if user == "me":
        token = os.environ["MY_API_TOKEN"]
    else:
        token = os.environ["HELPDESK_API_TOKEN"]
    if prod:
        url = "https://engine.netmgmt.utsc.utoronto.ca/api"
    else:
        url = "https://dev.engine.netmgmt.utsc.utoronto.ca/api"
    run(
        f"curl -H 'Authorization: Token {token}' -H 'Accept: application/json;' "
        + f"-H 'Content-Type: application/json' -X {method} {url}/{endpoint}"
    )
