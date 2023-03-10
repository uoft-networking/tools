from nautobot.extras.registry import DatasourceContent
from nautobot.extras.datasources.git import GitRepository



def refresh_device_types(
    repository_record: GitRepository, job_result, delete=False
):
    """Callback for GitRepository updates - refresh Device Types managed by it."""
    if "nautobot.device_types" not in repository_record.provided_contents or delete:
        # This repository is defined not to provide DeviceType records.
        # In a more complete worked example, we might want to iterate over any
        # DeviceType records that might have been previously created by this GitRepository
        # and ensure their deletion, but for now this is a no-op.
        return

    # This datasource type will be removed. for now it's a no-op
    return
    
    


# Register that DeviceType records can be loaded from a Git repository,
# and register the callback function used to do so
datasource_contents = [
    (
        "extras.gitrepository",  # datasource class we are registering for
        DatasourceContent(
            name="Device Types",  # human-readable name to display in the UI
            content_identifier="nautobot.device_types",  # internal slug to identify the data type
            icon="mdi-archive-sync",  # Material Design Icons icon to use in UI
            callback=refresh_device_types,  # callback function on GitRepository refresh
        ),
    )
]
