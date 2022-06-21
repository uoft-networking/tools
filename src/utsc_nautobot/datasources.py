import os
from pathlib import Path

import yaml
from nautobot.extras.choices import LogLevelChoices
from nautobot.extras.registry import DatasourceContent
from nautobot.dcim.models import (
    DeviceType,
    Manufacturer,
    device_component_templates as dct,
)


def refresh_single_device_type(model_file: Path, job_result):
    with model_file.open() as f:
        data = yaml.safe_load(f)

    components = {
        'console-ports': dct.ConsolePortTemplate,
        'console-server-ports': dct.ConsoleServerPortTemplate,
        'power-ports': dct.PowerPortTemplate,
        'power-outlets': dct.PowerOutletTemplate,
        'interfaces': dct.InterfaceTemplate,
        'front-ports': dct.FrontPortTemplate,
        'rear-ports': dct.RearPortTemplate,
        'device-bays': dct.DeviceBayTemplate,
        'module-bays': dct.DeviceBayTemplate # Nautobot doesn't seem to support module bays...
    }

    # Create or update a DeviceType record based on the provided data
    dt: DeviceType
    dt, _ = DeviceType.objects.update_or_create(
        manufacturer=(
            Manufacturer.objects.update_or_create(name=data["manufacturer"])[0]
        ),
        model=data["model"],
        slug=data["slug"],
        part_number=data["part_number"],
        u_height=data["u_height"],
        is_full_depth=data["is_full_depth"],
        subdevice_role="parent",
    )

    for name, model in components.items():
        for entry in data.get(name, []):
            model.objects.update_or_create(device_type=dt, **entry)

    dt.validated_save()

    # Record the outcome in the JobResult record
    job_result.log(
        "Successfully created/updated device type",
        obj=dt,
        level_choice=LogLevelChoices.LOG_SUCCESS,
        grouping="device_types",
    )


def refresh_device_types(repository_record, job_result, delete=False):
    """Callback for GitRepository updates - refresh Device Types managed by it."""
    if "nautobot.device_types" not in repository_record.provided_contents or delete:
        # This repository is defined not to provide DeviceType records.
        # In a more complete worked example, we might want to iterate over any
        # DeviceType records that might have been previously created by this GitRepository
        # and ensure their deletion, but for now this is a no-op.
        return

    # We have decided that a Git repository can provide YAML files in a
    # /device-types/ directory at the repository root.
    dt_path = Path(os.path.join(repository_record.filesystem_path, "device-types"))
    for manufacturer in dt_path.iterdir():
        for model_file in manufacturer.iterdir():
            refresh_single_device_type(model_file, job_result)
    # for filename in os.listdir(dt_path):
    #     with open(os.path.join(dt_path, filename)) as fd:
    #         data = yaml.safe_load(fd)

    #


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
