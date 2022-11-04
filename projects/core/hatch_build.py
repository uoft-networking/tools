from hatchling.metadata.plugin.interface import MetadataHookInterface


class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict):
        """
        This updates the metadata mapping of the `project` table in-place.
        """
        # All projects which depend on uoft_core will have custom logic here.
        pass
