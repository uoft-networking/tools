from pants.backend.python.util_rules.package_dists import SetupKwargs, SetupKwargsRequest
from pants.engine.target import Target
from pants.engine.rules import rule, implicitly
from pants.engine.fs import PathGlobs
from pants.engine.intrinsics import get_digest_contents
from pants.engine.unions import UnionRule


from setuptools_scm import get_version, ScmVersion


class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, target: Target) -> bool:
        return True


def uoft_version_scheme(version: ScmVersion) -> str:
    """Custom version scheme for uoft packages."""
    if version.exact:
        return version.format_with("{tag}")
    else:
        return version.format_with("{tag}.post{distance}")


@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    new_kwargs = {}
    if "name" not in request.explicit_kwargs:
        path = request.target.residence_dir
        name = path.partition('src/')[2].replace('/', '.') # ex: src/uoft/aruba -> uoft.aruba
        new_kwargs["name"] = name
    if "long_description" not in request.explicit_kwargs:
        digest_contents = await get_digest_contents(
            **implicitly(PathGlobs([f"{request.target.residence_dir}/README.md"]))
        )
        if not digest_contents:
            # TODO: log warning that README.md not found
            pass
        else:
            long_description = digest_contents[0].content.decode()
            new_kwargs["long_description"] = long_description
            new_kwargs["long_description_content_type"] = "text/markdown"
    if "version" not in request.explicit_kwargs:
        version = get_version(version_scheme=uoft_version_scheme, local_scheme="no-local-version")
        new_kwargs["version"] = version
    return SetupKwargs({**request.explicit_kwargs, **new_kwargs}, address=request.target.address)


def rules():
    return [
        setup_kwargs_plugin,
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]
