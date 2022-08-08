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


def refresh_single_device_type(model_file: Path) -> DeviceType:
    with model_file.open() as f:
        data = yaml.safe_load(f)

    components = {
        "console-ports": dct.ConsolePortTemplate,
        "console-server-ports": dct.ConsoleServerPortTemplate,
        "power-ports": dct.PowerPortTemplate,
        "power-outlets": dct.PowerOutletTemplate,
        "interfaces": dct.InterfaceTemplate,
        "front-ports": dct.FrontPortTemplate,
        "rear-ports": dct.RearPortTemplate,
        "device-bays": dct.DeviceBayTemplate,
        "module-bays": dct.DeviceBayTemplate,  # Nautobot doesn't seem to support module bays...
    }

    # Create or update a DeviceType record based on the provided data
    mfg, _ = Manufacturer.objects.update_or_create(name=data["manufacturer"])
    defaults = dict(
        subdevice_role = 'parent' if 'device-type' in str(model_file) else 'child'
    )
    if model := data.get("model"): defaults['model'] = model
    if part_number := data.get("part_number"): defaults['part_number'] = part_number
    if u_height := data.get("u_height"): defaults['u_height'] = u_height
    if is_full_depth := data.get("is_full_depth"): defaults['is_full_depth'] = is_full_depth
    if comments := data.get("comments"): defaults['comments'] = comments
    dt: DeviceType
    dt, _ = DeviceType.objects.update_or_create(
        manufacturer=mfg,
        slug=data["slug"],
        defaults=defaults
    )

    for name, model in components.items():
        for entry in data.get(name, []):
            entry_name = entry['name']
            model.objects.update_or_create(device_type=dt, name=entry_name, defaults=entry)

    dt.validated_save()
    return dt


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
            dt = refresh_single_device_type(model_file)

            # Record the outcome in the JobResult record
            job_result.log(
                "Successfully created/updated device type",
                obj=dt,
                level_choice=LogLevelChoices.LOG_SUCCESS,
                grouping="device_types",
            )


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
