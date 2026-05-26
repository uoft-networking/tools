from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules, goal_rule, rule, UnionRule

from pants.core.util_rules.external_tool import ExternalTool, ExportableTool, TemplatedExternalTool, download_external_tool


class Uv(ExternalTool):
    options_scope = "uv"
    help = "Astral's uv python management tool"

    default_version = "0.11.4"
    default_known_versions = [
        "0.11.4|macos_arm64 |9b9cb6c6f58c3246dbf3351ed4e97c500bc3266f5f237d2fd620b66e1c31dc56|20698302",
        "0.11.4|macos_x86_64|c326edaf3fd492f53d1c58777f3459c0d87bf9dae8d89e80aec4b0da6622dcf3|22340489",
        "0.11.4|linux_arm64 |f5aa91bba0b98d85a4e5262e2847f9ab2273c754f6374dff62b37ef18c65a2e7|22398832",
        "0.11.4|linux_x86_64|12f9a192bb32d70470aa22cbd2a193d1323a3f58f6ac5f9e3866aaca760c98c6|23954796",
    ]

    platform_mapping = {
            "macos_arm64": "aarch64-apple-darwin",
            "macos_x86_64": "x86_64-apple-darwin",
            "linux_arm64": "aarch64-unknown-linux-gnu",
            "linux_x86_64": "x86_64-unknown-linux-gnu",
        }

    def generate_url(self, plat: Platform) -> str:
        platform = self.platform_mapping[plat.value]
        return (
            f"https://github.com/astral-sh/uv/releases/download/{self.version}/uv-{platform}.tar.gz"
        )

    def generate_exe(self, plat: Platform) -> str:
        platform = self.platform_mapping[plat.value]
        return f"./uv-{platform}/uv"


class UvSubsystem(GoalSubsystem):
    name = "uv-tool"
    help = "Run uv to manage Python dependencies"


class UvGoal(Goal):
    """Run uv to manage Python dependencies"""
    subsystem_cls = UvSubsystem
    environment_behavior = Goal.EnvironmentBehavior.LOCAL_ONLY


@goal_rule
async def run_uv(uv: Uv, plat: Platform) -> UvGoal:
    downloaded_uv = await download_external_tool(uv.get_request(plat))
    return UvGoal(0)


def rules():
    return (
        *collect_rules(), 
        UnionRule(ExportableTool, Uv)
    )
