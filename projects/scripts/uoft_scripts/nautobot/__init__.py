import typing as t
import re

from uoft_core.types import SecretStr
from uoft_core import BaseSettings, Field, StrEnum, logging
from uoft_core.console import console

if t.TYPE_CHECKING:
    from pynautobot.models.extras import Record
    from pynautobot.models.dcim import Devices as NautobotDeviceRecord

# NOTE: this really aught to live in a uoft-nautobot package, dedicated to code surrounding the nautobot rest api,
# but there happens to already be a uoft_nautobot package, which is actually a uoft-centric nautobot plugin and
# should actually be called nautobot-uoft,
# TODO: move/rename uoft_nautobot to nautobot-uoft and create a uoft_nautobot project for this code.

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Settings for the nautobot_cli application."""

    url: str = Field(..., title="Nautobot server URL")
    token: SecretStr = Field(..., title="Nautobot API Token")

    class Config(BaseSettings.Config):
        app_name = "nautobot-cli"

    def api_connection(self):
        import pynautobot
        return pynautobot.api(url=self.url, token=self.token.get_secret_value(), threading=True)


class DevSettings(Settings):
    class Config(BaseSettings.Config):  # pyright: ignore[reportIncompatibleVariableOverride]
        app_name = "nautobot-cli-dev"


class OnOrphanAction(StrEnum):
    prompt = "prompt"
    delete = "delete"
    backport = "backport"
    skip = "skip"


class ComplianceReportGoal(StrEnum):
    add = "add"
    remove = "remove"


def get_settings(dev: bool = False):
    if dev:
        return DevSettings.from_cache()
    return Settings.from_cache()


DEV_NB_API = None
PROD_NB_API = None


def get_api(dev: bool = False):
    global DEV_NB_API, PROD_NB_API
    if dev:
        if DEV_NB_API is None:
            DEV_NB_API = get_settings(dev).api_connection()
        return DEV_NB_API
    else:
        if PROD_NB_API is None:
            PROD_NB_API = get_settings(dev).api_connection()
        return PROD_NB_API

def run_job(dev: bool, job_name: str, data: dict):
    import time
    from pynautobot.models.extras import Jobs, JobResults, Record
    nb = get_api(dev)
    con = console()
    job = t.cast(Jobs | None, nb.extras.jobs.get(name=job_name))
    assert job, f"Job '{job_name}' not found in Nautobot"
    job_result = t.cast(JobResults, nb.extras.jobs.run(job_id=job.id, data=data).job_result)  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    con.print(f"A new '{job_name}' job run has been triggered. Job status / results can be found here:")
    url = t.cast(str, job_result.url).replace("/api/", "/")
    con.print(f"[link={url}]{url}[/link]")
    con.print("Waiting for job to complete...")
    while True:
        new_result = t.cast(JobResults, nb.extras.job_results.get(job_result.id))
        status = t.cast(str, t.cast(Record, new_result.status).value)
        if status not in ["STARTED", "PENDING"]:
            con.print(" ")
            break
        con.print(".", end="")
        time.sleep(1)
    logger.success("Job completed with status: " + status)
    if status != "SUCCESS":
        logger.error("Job failed")
        logger.error(new_result)
    return new_result


@t.no_type_check
def update_golden_config_repo(dev=False):
    nb = get_api(dev)
    gitrepo = nb.extras.git_repositories.get(name="golden_config_templates")
    job_result = run_job(dev, "Git Repository: Sync", {"repository": gitrepo.id})
    return job_result

def get_intended_config(switch_hostname: "str | NautobotDeviceRecord", update_templates_repo=False) -> str:
    nb = get_api(dev=False)
    if isinstance(switch_hostname, str):
        switch = t.cast("NautobotDeviceRecord", nb.dcim.devices.get(name=switch_hostname))
    else:
        switch = switch_hostname

    if update_templates_repo:
        logger.info("Updating templates repository before generating intended config...")
        update_golden_config_repo()

    # trigger intended config generation
    logger.info(f"Generating fresh intended config for {switch_hostname}...")
    run_job(dev=False, job_name="Generate Intended Configurations", data=dict(device=[switch.id]))

    intended_config = t.cast(
        str, t.cast("Record", nb.plugins.golden_config.config_postprocessing.get(switch.id)).config
    )

    return intended_config


def _group_config(config: str) -> list[str]:
    # Break up the config snippet into a list of lines.
    # Group lines that start with an indent in with the non-indented line above them
    return re.split(r"\n(?!\s)", config)


def filter_config(config: str, filters: list[str], sub_filters: list[str] | None = None, top_level_only: bool = False):
    """
    Filters and extracts configuration chunks from a given configuration string based on specified filters.
    Args:
        config: The configuration string to be filtered.
        filters: List of regular expression patterns to match against the top-level
            lines of each configuration chunk.
        sub_filters: List of regular expression patterns to further filter sub-lines
            within matched chunks. Defaults to None.
        top_level_only: If True, only the top-level line of each matched chunk is
            included in the result. If False, the entire chunk or filtered sub-lines are included.
            Defaults to False.
    Returns:
        A list of configuration chunks or lines that match the specified filters.
    Notes:
        - The configuration is first grouped into chunks,
          where each chunk starts with a non-indented line followed by its indented sub-lines.
        - If `sub_filters` is provided, only sub-lines within matched chunks that match any of
          the `sub_filters` are included.
        - If `top_level_only` is True, only the first line of each matched chunk is returned,
          and `sub_filters` is ignored.
    """

    grouped_config = _group_config(config)
    sub_filters = sub_filters or []
    # Break up the config snippet into a list of lines.
    # Group lines that start with an indent in with the non-indented line above them
    res: list[str] = []
    for chunk in grouped_config:
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        if not any([re.search(f, lines[0]) for f in filters]):
            continue
        if not sub_filters:
            if top_level_only:
                res.append(lines[0])
            else:
                # add the whole chunk to res
                res.append("\n".join(lines))
        else:
            # filter the chunk by sub_filters
            filtered_chunk = [lines[0]]
            for line in lines[1:]:
                if any([re.search(f, line) for f in sub_filters]):
                    filtered_chunk.append(line)
            if len(filtered_chunk) > 1:
                res.append("\n".join(filtered_chunk))
    return res


def get_minimum_viable_config(switch_hostname: "str | NautobotDeviceRecord") -> list[str]:
    intended_config = get_intended_config(switch_hostname)
    res = filter_config(config=intended_config, filters=["vrf instance"], top_level_only=True)
    res.extend(
        filter_config(
            config=intended_config,
            filters=[
                "hostname",
                "radius-server",
                "ip radius",
                "ip address",
                "enable",
                "aaa",
                "ip route",
                "^interface Management1",
            ],
        )
    )
    res.extend(
        filter_config(
            config=intended_config,
            filters=[
                "management ssh",
            ],
            sub_filters=[
                "authentication",  # we only want the authentication mode bits, none of the ACL stuff
            ],
        )
    )
    return res
