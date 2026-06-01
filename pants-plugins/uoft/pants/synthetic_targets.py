from dataclasses import dataclass
from pathlib import Path
from logging import getLogger

from pants.engine.internals.synthetic_targets import (
    SyntheticAddressMaps,
    SyntheticTargetsRequest,
)
from pants.engine.internals.target_adaptor import TargetAdaptor
from pants.engine.rules import collect_rules, rule

APPS_DIR = "src/apps"

logger = getLogger(__name__)


@dataclass(frozen=True)
class SyntheticPythonAppTargetsRequest(SyntheticTargetsRequest):
    pass


@rule
async def python_app_synthetic_targets(request: SyntheticPythonAppTargetsRequest) -> SyntheticAddressMaps:
    if not request.path.startswith(APPS_DIR):
        return SyntheticAddressMaps()
    logger.info(f"Generating synthetic targets for {request} at {request.path}")
    rpath = Path(request.path)
    if not rpath.is_dir():
        return SyntheticAddressMaps()
    target_adaptors = []
    for file in rpath.glob("*.py"):
        name = file.stem.replace("_", "-").lower()
        target_adaptors.append(
            TargetAdaptor(
                "python_source",
                f"{name}-src",
                "synthetic target",
                source=str(file.relative_to(request.path)),
            )
        )
        target_adaptors.append(
            TargetAdaptor(
                "pex_binary",
                name,
                "synthetic target",
                dependencies=[f":{name}-src"],
                entry_point=str(file.relative_to(request.path)),
                include_tools=True,
                output_path=f"apps/{name}.pex",
                scie="eager",
            )
        )
        # target_adaptors.append(
        #     TargetAdaptor(
        #         "scie_binary",
        #         f'{name}-scie',
        #         "synthetic target", # pyright: ignore[reportArgumentType]
        #         dependencies=[f":{name}-pex"],
        #         binary_name=name,
        #     )
        # )
    return SyntheticAddressMaps.for_targets_request(request, [("BUILD.python-apps", target_adaptors)])


def rules():
    return (
        *collect_rules(),
        *SyntheticPythonAppTargetsRequest.rules(),
    )
