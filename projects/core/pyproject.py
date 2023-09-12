from hatchling.metadata.plugin.interface import MetadataHookInterface
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from setuptools_scm import get_version

V = get_version(
    root="../..", relative_to=__file__, version_scheme="post-release"
)


class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict):
        """
        This updates the metadata mapping of the `project` table in-place.
        """
        
        metadata["version"] = V
        new_deps = []
        for dep in metadata["dependencies"]:
            if "uoft_" in dep:
                dep = dep.partition(" ")[0]

                # if v is not a clean version number (ie contains a '.post###' segment or a '+g{hash}' segment),
                # we are likely in a dev environment or a CI environment or a specific repo commit that's
                # been locally cloned for installation. In that case, we want to reference all repo-internal
                # projects by relative direct reference, not by version number
                if ".post" in V or "+g" in V:
                    project_name = dep.partition("_")[2]
                    dep += " @ {root:uri}/../" + project_name
                    # ex: 'uoft_core' becomes 'uoft_core @ {root:uri}/../core'

                # if v is a clean version number, we are likely installing from PYPI, and we want to
                # reference all repo-internal projects by version number, not by relative direct reference
                else:
                    dep += f" == {V}"

            new_deps.append(dep)
        metadata["dependencies"] = new_deps
