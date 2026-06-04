from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules, goal_rule, UnionRule

from pants.core.util_rules.external_tool import ExternalTool, ExportableTool


class Ripgrep(ExternalTool):
    options_scope = "ripgrep"
    help = "BurntSushi's ripgrep search tool"

    default_version = "15.1.0"
    default_known_versions = [
        "15.1.0|macos_arm64 |378e973289176ca0c6054054ee7f631a065874a352bf43f0fa60ef079b6ba715|1777930",
        "15.1.0|macos_x86_64|64811cb24e77cac3057d6c40b63ac9becf9082eedd54ca411b475b755d334882|1894127",
        "15.1.0|linux_arm64 |2b661c6ef508e902f388e9098d9c4c5aca72c87b55922d94abdba830b4dc885e|1869959",
        "15.1.0|linux_x86_64|1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599|2263077",
    ]

    platform_mapping = {
            "macos_arm64": "aarch64-apple-darwin",
            "macos_x86_64": "x86_64-apple-darwin",
            "linux_arm64": "aarch64-unknown-linux-gnu",
            "linux_x86_64": "x86_64-unknown-linux-musl",
        }

    def generate_url(self, plat: Platform) -> str:
        platform = self.platform_mapping[plat.value]
        return (
            f"https://github.com/BurntSushi/ripgrep/releases/download/{self.version}/ripgrep-{self.version}-{platform}.tar.gz"
        )

    def generate_exe(self, plat: Platform) -> str:
        platform = self.platform_mapping[plat.value]
        return f"./ripgrep-{self.version}-{platform}/rg"


class RipgrepSubsystem(GoalSubsystem):
    name = "ripgrep-tool"
    help = "Placeholder to make ripgrep pants-exportable"


class RipgrepGoal(Goal):
    """Placeholder to make ripgrep pants-exportable"""
    subsystem_cls = RipgrepSubsystem
    environment_behavior = Goal.EnvironmentBehavior.LOCAL_ONLY


@goal_rule
async def make_ripgrep_exportable(ripgrep: Ripgrep, plat: Platform) -> RipgrepGoal:
    raise NotImplementedError("This goal is not yet implemented. Please export and use ripgrep directly for now.")


def rules():
    return (
        *collect_rules(), 
        UnionRule(ExportableTool, Ripgrep)
    )
