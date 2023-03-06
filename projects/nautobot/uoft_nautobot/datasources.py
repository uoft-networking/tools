from pathlib import Path

import yaml
from nautobot.extras.choices import LogLevelChoices
from nautobot.extras.registry import DatasourceContent
from nautobot.extras.datasources.git import GitRepository
from nautobot.dcim.models import (
    DeviceType,
    Manufacturer,
    device_component_templates as dct,
)
from django.conf import settings
from django.db.utils import IntegrityError

from pydantic import BaseModel, Field
from typing import Literal, Iterable
from rich.progress import track


class DeviceComponent(BaseModel):
    def to_nautobot(
        self,
        device_type: DeviceType,
        exclude_fields: dict | set | None = None,
        overrides: dict | None = None,
        **kwargs,
    ):
        # map the class name of the class that implements this interface to the
        # corresponding Nautobot DeviceComponentTemplate subclass

        # Ex : ConsolePort -> dct.ConsolePortTemplate
        class_name = f"{self.__class__.__name__}Template"

        if exclude_fields is None:
            exclude_fields = {}
        payload = self.dict(exclude=exclude_fields)
        if "label" in payload and payload["label"] is None:
            payload["label"] = ""
        for k, v in (overrides or {}).items():
            payload[k] = v
        return getattr(dct, class_name).objects.update_or_create(
            device_type=device_type, name=payload["name"], defaults=payload
        )


class ConsolePort(DeviceComponent):
    name: str
    type: Literal[
        "de-9",
        "db-25",
        "rj-11",
        "rj-12",
        "rj-45",
        "mini-din-8",
        "usb-a",
        "usb-b",
        "usb-c",
        "usb-mini-a",
        "usb-mini-b",
        "usb-micro-a",
        "usb-micro-b",
        "usb-micro-ab",
        "other",
    ]
    label: str | None = None

    def to_nautobot(self, device_type: DeviceType, **kwargs) -> dct.ConsolePortTemplate:
        return super().to_nautobot(device_type, **kwargs)


class PowerPort(DeviceComponent):
    name: str
    type: Literal[
        "iec-60320-c6",
        "iec-60320-c8",
        "iec-60320-c14",
        "iec-60320-c16",
        "iec-60320-c20",
        "iec-60320-c22",
        "iec-60309-p-n-e-4h",
        "iec-60309-p-n-e-6h",
        "iec-60309-p-n-e-9h",
        "iec-60309-2p-e-4h",
        "iec-60309-2p-e-6h",
        "iec-60309-2p-e-9h",
        "iec-60309-3p-e-4h",
        "iec-60309-3p-e-6h",
        "iec-60309-3p-e-9h",
        "iec-60309-3p-n-e-4h",
        "iec-60309-3p-n-e-6h",
        "iec-60309-3p-n-e-9h",
        "nema-1-15p",
        "nema-5-15p",
        "nema-5-20p",
        "nema-5-30p",
        "nema-5-50p",
        "nema-6-15p",
        "nema-6-20p",
        "nema-6-30p",
        "nema-6-50p",
        "nema-10-30p",
        "nema-10-50p",
        "nema-14-20p",
        "nema-14-30p",
        "nema-14-50p",
        "nema-14-60p",
        "nema-15-15p",
        "nema-15-20p",
        "nema-15-30p",
        "nema-15-50p",
        "nema-15-60p",
        "nema-l1-15p",
        "nema-l5-15p",
        "nema-l5-20p",
        "nema-l5-30p",
        "nema-l5-50p",
        "nema-l6-15p",
        "nema-l6-20p",
        "nema-l6-30p",
        "nema-l6-50p",
        "nema-l10-30p",
        "nema-l14-20p",
        "nema-l14-30p",
        "nema-l14-50p",
        "nema-l14-60p",
        "nema-l15-20p",
        "nema-l15-30p",
        "nema-l15-50p",
        "nema-l15-60p",
        "nema-l21-20p",
        "nema-l21-30p",
        "nema-l22-30p",
        "cs6361c",
        "cs6365c",
        "cs8165c",
        "cs8265c",
        "cs8365c",
        "cs8465c",
        "ita-c",
        "ita-e",
        "ita-f",
        "ita-ef",
        "ita-g",
        "ita-h",
        "ita-i",
        "ita-j",
        "ita-k",
        "ita-l",
        "ita-m",
        "ita-n",
        "ita-o",
        "usb-a",
        "usb-b",
        "usb-c",
        "usb-mini-a",
        "usb-mini-b",
        "usb-micro-a",
        "usb-micro-b",
        "usb-micro-ab",
        "usb-3-b",
        "usb-3-micro-b",
        "dc-terminal",
        "saf-d-grid",
        "ubiquiti-smartpower",
        "hardwired",
        "other",
    ]
    label: str | None = None
    maximum_draw: int | None = None
    allocated_draw: int | None = None

    def to_nautobot(self, device_type: DeviceType, **kwargs) -> dct.PowerPortTemplate:
        return super().to_nautobot(device_type, **kwargs)


class PowerOutlet(DeviceComponent):
    name: str
    type: Literal[
        "iec-60320-c5",
        "iec-60320-c7",
        "iec-60320-c13",
        "iec-60320-c15",
        "iec-60320-c19",
        "iec-60320-c21",
        "iec-60309-p-n-e-4h",
        "iec-60309-p-n-e-6h",
        "iec-60309-p-n-e-9h",
        "iec-60309-2p-e-4h",
        "iec-60309-2p-e-6h",
        "iec-60309-2p-e-9h",
        "iec-60309-3p-e-4h",
        "iec-60309-3p-e-6h",
        "iec-60309-3p-e-9h",
        "iec-60309-3p-n-e-4h",
        "iec-60309-3p-n-e-6h",
        "iec-60309-3p-n-e-9h",
        "nema-1-15r",
        "nema-5-15r",
        "nema-5-20r",
        "nema-5-30r",
        "nema-5-50r",
        "nema-6-15r",
        "nema-6-20r",
        "nema-6-30r",
        "nema-6-50r",
        "nema-10-30r",
        "nema-10-50r",
        "nema-14-20r",
        "nema-14-30r",
        "nema-14-50r",
        "nema-14-60r",
        "nema-15-15r",
        "nema-15-20r",
        "nema-15-30r",
        "nema-15-50r",
        "nema-15-60r",
        "nema-l1-15r",
        "nema-l5-15r",
        "nema-l5-20r",
        "nema-l5-30r",
        "nema-l5-50r",
        "nema-l6-15r",
        "nema-l6-20r",
        "nema-l6-30r",
        "nema-l6-50r",
        "nema-l10-30r",
        "nema-l14-20r",
        "nema-l14-30r",
        "nema-l14-50r",
        "nema-l14-60r",
        "nema-l15-20r",
        "nema-l15-30r",
        "nema-l15-50r",
        "nema-l15-60r",
        "nema-l21-20r",
        "nema-l21-30r",
        "nema-l22-30r",
        "CS6360C",
        "CS6364C",
        "CS8164C",
        "CS8264C",
        "CS8364C",
        "CS8464C",
        "ita-e",
        "ita-f",
        "ita-g",
        "ita-h",
        "ita-i",
        "ita-j",
        "ita-k",
        "ita-l",
        "ita-m",
        "ita-n",
        "ita-o",
        "ita-multistandard",
        "usb-a",
        "usb-micro-b",
        "usb-c",
        "dc-terminal",
        "hdot-cx",
        "saf-d-grid",
        "ubiquiti-smartpower",
        "hardwired",
        "other",
    ]
    label: str | None = None
    power_port: str | None = None
    feed_leg: Literal["A", "B", "C", ""] | None = ""

    def to_nautobot(self, device_type: DeviceType, **kwargs) -> dct.PowerOutletTemplate:
        overrides = {}

        if self.power_port:
            power_port = dct.PowerPortTemplate.objects.get(
                device_type=device_type, name=self.power_port
            )
            if power_port is None:
                raise ValueError(
                    f"Power port {self.power_port} not found on device type {device_type}"
                )
            overrides["power_port"] = power_port

        return super().to_nautobot(device_type, overrides=overrides, **kwargs)


class Interface(DeviceComponent):
    name: str
    type: Literal[
        "virtual",
        "bridge",
        "lag",
        "100base-fx",
        "100base-lfx",
        "100base-tx",
        "100base-t1",
        "1000base-t",
        "1000base-x-gbic",
        "1000base-x-sfp",
        "2.5gbase-t",
        "5gbase-t",
        "10gbase-t",
        "10gbase-cx4",
        "10gbase-x-sfpp",
        "10gbase-x-xfp",
        "10gbase-x-xenpak",
        "10gbase-x-x2",
        "25gbase-x-sfp28",
        "40gbase-x-qsfpp",
        "50gbase-x-sfp28",
        "100gbase-x-cfp",
        "100gbase-x-cfp2",
        "100gbase-x-cfp4",
        "100gbase-x-cpak",
        "100gbase-x-qsfp28",
        "200gbase-x-cfp2",
        "200gbase-x-qsfp56",
        "400gbase-x-qsfpdd",
        "400gbase-x-osfp",
        "ieee802.11a",
        "ieee802.11g",
        "ieee802.11n",
        "ieee802.11ac",
        "ieee802.11ad",
        "ieee802.11ax",
        "ieee802.15.1",
        "gsm",
        "cdma",
        "lte",
        "sonet-oc3",
        "sonet-oc12",
        "sonet-oc48",
        "sonet-oc192",
        "sonet-oc768",
        "sonet-oc1920",
        "sonet-oc3840",
        "1gfc-sfp",
        "2gfc-sfp",
        "4gfc-sfp",
        "8gfc-sfpp",
        "16gfc-sfpp",
        "32gfc-sfp28",
        "64gfc-qsfpp",
        "128gfc-qsfp28",
        "infiniband-sdr",
        "infiniband-ddr",
        "infiniband-qdr",
        "infiniband-fdr10",
        "infiniband-fdr",
        "infiniband-edr",
        "infiniband-hdr",
        "infiniband-ndr",
        "infiniband-xdr",
        "t1",
        "e1",
        "t3",
        "e3",
        "xdsl",
        "docsis",
        "cisco-stackwise",
        "cisco-stackwise-plus",
        "cisco-flexstack",
        "cisco-flexstack-plus",
        "cisco-stackwise-80",
        "cisco-stackwise-160",
        "cisco-stackwise-320",
        "cisco-stackwise-480",
        "juniper-vcp",
        "extreme-summitstack",
        "extreme-summitstack-128",
        "extreme-summitstack-256",
        "extreme-summitstack-512",
        "gpon",
        "xg-pon",
        "xgs-pon",
        "ng-pon2",
        "epon",
        "10g-epon",
        "other",
    ]
    poe_mode: Literal["pd", "pse"] | None = None
    poe_type: Literal[
        "type1-ieee802.3af",
        "type2-ieee802.3at",
        "type3-ieee802.3bt",
        "type4-ieee802.3bt",
        "passive-24v-2pair",
        "passive-24v-4pair",
        "passive-48v-2pair",
        "passive-48v-4pair",
    ] | None = None
    mgmt_only: bool | None = None

    def to_nautobot(self, device_type: DeviceType, **kwargs) -> dct.InterfaceTemplate:
        if self.mgmt_only is None:
            self.mgmt_only = False

        return super().to_nautobot(
            device_type, exclude_fields={"poe_mode", "poe_type"}, **kwargs
        )


class FrontPort(DeviceComponent):
    name: str
    type: Literal[
        "8p8c",
        "8p6c",
        "8p4c",
        "8p2c",
        "6p6c",
        "6p4c",
        "6p2c",
        "4p4c",
        "4p2c",
        "gg45",
        "tera-4p",
        "tera-2p",
        "tera-1p",
        "110-punch",
        "bnc",
        "f",
        "n",
        "mrj21",
        "st",
        "sc",
        "sc-apc",
        "fc",
        "lc",
        "lc-apc",
        "mtrj",
        "mpo",
        "lsh",
        "lsh-apc",
        "splice",
        "cs",
        "sn",
        "sma-905",
        "sma-906",
        "urm-p2",
        "urm-p4",
        "urm-p8",
        "other",
    ]
    label: str | None = None
    color: str | None = None
    rear_port: str | None = None
    rear_port_position: int | None = 1

    def to_nautobot(self, device_type: DeviceType, orig_data: "DeviceTypeYAML") -> dct.FrontPortTemplate:
        overrides = {}
        if self.rear_port:
            assert orig_data.rear_ports, "No rear ports defined on parent device type"

            rear_port = dct.RearPortTemplate.objects.get(
                device_type=device_type, name=self.rear_port
            )
            if rear_port is None:
                raise ValueError(
                    f"Rear port {self.rear_port} not found on device type {device_type}"
                )
            overrides = {"rear_port": rear_port}

        return super().to_nautobot(
            device_type,
            exclude_fields={"color"},
            orig_data=orig_data,
            overrides=overrides,
        )


class RearPort(DeviceComponent):
    name: str
    type: Literal[
        "8p8c",
        "8p6c",
        "8p4c",
        "8p2c",
        "6p6c",
        "6p4c",
        "6p2c",
        "4p4c",
        "4p2c",
        "gg45",
        "tera-4p",
        "tera-2p",
        "tera-1p",
        "110-punch",
        "bnc",
        "f",
        "n",
        "mrj21",
        "st",
        "sc",
        "sc-apc",
        "fc",
        "lc",
        "lc-apc",
        "mtrj",
        "mpo",
        "lsh",
        "lsh-apc",
        "splice",
        "cs",
        "sn",
        "sma-905",
        "sma-906",
        "urm-p2",
        "urm-p4",
        "urm-p8",
        "other",
    ]
    positions: int | None = 1
    label: str | None = None
    color: str | None = None

    def to_nautobot(self, **kwargs) -> dct.RearPortTemplate:
        return super().to_nautobot(**kwargs, exclude_fields={"color"})


class ModuleBay(DeviceComponent):
    name: str
    label: str | None = None
    position: str | None = None


class DeviceBay(DeviceComponent):
    name: str
    label: str | None = None

    def to_nautobot(self, **kwargs) -> dct.DeviceBayTemplate:
        return super().to_nautobot(**kwargs)


class InventoryItem(DeviceComponent):
    name: str
    label: str | None = None
    manufacturer: str | None = None
    part_id: str | None = None


class Weight(DeviceComponent):
    value: float
    unit: Literal["g", "kg", "lb", "oz"]


class DeviceTypeYAML(BaseModel):
    """A Pydantic model for a DeviceType YAML file."""

    manufacturer: str
    model: str
    slug: str
    part_number: str | None = ""
    u_height: int | None = 1
    is_full_depth: bool | None = False
    airflow: Literal[
        "front-to-rear",
        "rear-to-front",
        "left-to-right",
        "right-to-left",
        "side-to-rear",
        "passive",
    ] | None = None
    weight: list[Weight] | None = None
    subdevice_role: Literal["parent", "child", ""] | None = ""
    console_ports: list[ConsolePort] | None = Field(None, alias="console-ports")
    console_server_ports: list[ConsolePort] | None = Field(
        None, alias="console-server-ports"
    )
    power_ports: list[PowerPort] | None = Field(None, alias="power-ports")
    power_outlets: list[PowerOutlet] | None = Field(None, alias="power-outlets")
    interfaces: list[Interface] | None = None
    front_ports: list[FrontPort] | None = Field(None, alias="front-ports")
    rear_ports: list[RearPort] | None = Field(None, alias="rear-ports")
    module_bays: list[ModuleBay] | None = Field(None, alias="module-bays")
    device_bays: list[DeviceBay] | None = Field(None, alias="device-bays")
    inventory_items: list[InventoryItem] | None = Field(None, alias="inventory-items")
    comments: str | None = ""

    class Config:
        extra = "forbid"

    def to_nautobot(self) -> DeviceType:
        """Convert a DeviceTypeYAML object to a DeviceType object."""

        # Temp workaround until https://github.com/netbox-community/devicetype-library/pull/1176 gets merged
        if self.slug == "ws-c3750g-12s-e":
            self.model = "Catalyst 3750G-12S-E"
        if self.slug == "ws-c3750g-12s-s":
            self.model = "Catalyst 3750G-12S-S"

        # Create or update a DeviceType record based on the provided data
        mfg, _ = Manufacturer.objects.update_or_create(name=self.manufacturer)
        if self.subdevice_role != "parent" and self.device_bays is not None and len(self.device_bays) > 0:
            # In Nautobot all device types which have device bays must have a subdevice role of parent
            self.subdevice_role = "parent"
            
        try:
            dt, _ = DeviceType.objects.update_or_create(
                manufacturer=mfg,
                slug=self.slug,
                model=self.model,
                defaults=dict(
                    model=self.model,
                    part_number=self.part_number,
                    u_height=self.u_height,
                    is_full_depth=self.is_full_depth,
                    subdevice_role=self.subdevice_role,
                    comments=self.comments,
                ),
            )
        except IntegrityError:
            dt = DeviceType.objects.get(manufacturer=mfg, slug=self.slug)

        # Create or update a DeviceComponentTemplate record for each component
        for component in [
            self.console_ports,
            self.console_server_ports,
            self.power_ports,
            self.power_outlets,
            self.interfaces,
            self.rear_ports,
            self.front_ports,
            # self.module_bays,  # Nautobot does not support module bays
            self.device_bays,
            # self.inventory_items,  # Nautobot does not support inventory items
        ]:
            if component is not None:
                for c in component:
                    c.to_nautobot(device_type=dt, orig_data=self)

        dt.validated_save()
        return dt


def refresh_single_device_type(model_file: Path) -> DeviceType:
    with model_file.open() as f:
        data = yaml.safe_load(f)

    dt_yaml = DeviceTypeYAML(**data)
    dt = dt_yaml.to_nautobot()
    return dt


def iterate_device_type_files(path: Path, interactive: bool) -> Iterable[Path]:
    """Iterate over all device type files in the repository."""
    models = list()
    target_manufacturers = settings.PLUGINS_CONFIG["uoft_nautobot"]["device_type_manufacturers"]
    
    for manufacturer in path.iterdir():
        if manufacturer.name in target_manufacturers:
            models.extend(manufacturer.iterdir())
    
    if interactive:
        return track(models, description="Loading device types")
    else:
        return models


def refresh_device_types(repository_record: GitRepository, job_result, delete=False, interactive=False):
    """Callback for GitRepository updates - refresh Device Types managed by it."""
    if "nautobot.device_types" not in repository_record.provided_contents or delete:
        # This repository is defined not to provide DeviceType records.
        # In a more complete worked example, we might want to iterate over any
        # DeviceType records that might have been previously created by this GitRepository
        # and ensure their deletion, but for now this is a no-op.
        return

    # We have decided that a Git repository can provide YAML files in a
    # /device-types/ directory at the repository root.
    git_repo_path = Path(repository_record.filesystem_path)
    dt_path = git_repo_path / "device-types"
    for model_file in iterate_device_type_files(dt_path, interactive):
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
