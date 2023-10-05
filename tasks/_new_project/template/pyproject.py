from hatchling.metadata.plugin.interface import MetadataHookInterface
from setuptools_scm import get_version
import os
from pathlib import Path

V = get_version(root="../..", relative_to=__file__, version_scheme="post-release")


class CustomMetadataHook(MetadataHookInterface):
    def is_rye_lock(self):
        # Not a great way to detect that we're being run from `rye lock`,
        # but pretty much the only effective way i know of
        return os.environ.get("PROJECT_ROOT")

    def is_release(self):
        # if v is not a clean version number (ie contains a '.post###' segment or a '+g{hash}' segment),
        # we are likely in a dev environment or a CI environment or a specific repo commit that's
        # been locally cloned for installation. In that case, we want to reference all repo-internal
        # projects by relative direct reference, not by version number
        return ".post" not in V and "+g" not in V

    def monorepo_root(self):
        return Path(self.root).parent.parent

    def local_dependencies(self, metadata: dict):
        """
        Returns a list of all uoft_* dependencies specified in this project's metadata
        """

        for dep in metadata["dependencies"]:
            if "uoft_" in dep:
                proj_name = dep.partition(" ")[0].partition("uoft_")[2]
                proj_dir = self.monorepo_root() / "projects" / proj_name
                if proj_dir.exists():
                    yield dep, proj_dir

    def update_local_dependency_specifications(self, metadata: dict):
        """
        for all uoft_* dependencies specified in this project's metadata,
        if those depenencies are also contained within this project's monorepo,
        We want to do one of several things:

        If we're cutting a new release (building a sdist or wheel for upload to PYPI),
        we want to add version numbers to the dependency specifications.
        ex: if V == '0.1.0', 'uoft_core' becomes 'uoft_core == 0.1.0'

        If we're installing from source (ex `pip install projects/{project}` or `pip install git+https://...`),
        we want to add relative direct references to the dependency specifications.

        If this hook is being called from within a `rye lock`, we want to do nothing.
        """
        deps = {dep: dep for dep in metadata["dependencies"]}
        for dep, project_dir in self.local_dependencies(metadata):
            if self.is_rye_lock():
                # We're running inside of rye lock
                deps[dep] = dep
            elif self.is_release():
                # We're building a release
                deps[dep] = f"{dep} == {V}"
            else:
                # We're installing from source
                deps[dep] = f"{dep} @ file://{project_dir}"

        metadata["dependencies"] = list(deps.values())

    def update(self, metadata: dict):
        """
        This updates the metadata mapping of the `project` table in-place.
        """

        metadata["version"] = V

        self.update_local_dependency_specifications(metadata)
