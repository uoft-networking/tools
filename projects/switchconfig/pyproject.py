from hatchling.metadata.plugin.interface import MetadataHookInterface
from setuptools_scm import get_version


class CustomMetadataHook(MetadataHookInterface):

    def update(self, metadata: dict):
        """
        This updates the metadata mapping of the `project` table in-place.
        """
        v = get_version(root='../..', relative_to=__file__)
        metadata['version'] = v
        for dep in metadata['dependencies'].copy():
            if 'uoft_core' in dep:
                metadata['dependencies'].remove(dep)
                metadata['dependencies'].append(f'uoft_core == {v}')