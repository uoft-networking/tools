from pathlib import Path


from django.core.management.base import BaseCommand
from django.conf import settings
from nautobot.extras.models import GitRepository
from nautobot.utilities.utils import NautobotFakeRequest
from nautobot.users.models import User
from pathlib import Path
from unittest.mock import MagicMock

import yaml
from nautobot.extras.datasources.git import GitRepository, ensure_git_repository
from nautobot.dcim.models import (
    DeviceType,
    Manufacturer,
    device_component_templates as dct,
)
from nautobot.dcim import choices as dct_choices
from django.conf import settings

from pydantic import BaseModel, Field, validator, root_validator
from typing import Literal, Iterable
from rich.progress import Progress, MofNCompleteColumn


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
        "",
    ]
    label: str | None = None
    maximum_draw: int | None = None
    allocated_draw: int | None = None

    @validator("type")
    def validate_type(cls, v):
        # temp workaround until https://github.com/nautobot/nautobot/issues/3398 is fixed
        if v not in dct_choices.PowerPortTypeChoices.values():
            return ""
        return v

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
    mgmt_only: bool | None = False

    @validator("type")
    def validate_type(cls, v):
        if v not in dct_choices.InterfaceTypeChoices.values():
            return "other"
        return v

    @validator("mgmt_only")
    def validate_mgmt_only(cls, v):
        if v is None:
            return False
        return v

    def to_nautobot(self, device_type: DeviceType, **kwargs) -> dct.InterfaceTemplate:
        return super().to_nautobot(device_type, **kwargs)


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
    rear_port: str | None = None
    rear_port_position: int | None = 1

    def to_nautobot(
        self, device_type: DeviceType, orig_data: "DeviceTypeYAML"
    ) -> dct.FrontPortTemplate:
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

    def to_nautobot(self, **kwargs) -> dct.RearPortTemplate:
        return super().to_nautobot(**kwargs)


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
    # airflow: Literal[
    #     "front-to-rear",
    #     "rear-to-front",
    #     "left-to-right",
    #     "right-to-left",
    #     "side-to-rear",
    #     "passive",
    # ] | None = None
    # weight: list[Weight] | None = None
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
    # module_bays: list[ModuleBay] | None = Field(None, alias="module-bays")
    device_bays: list[DeviceBay] | None = Field(None, alias="device-bays")
    # inventory_items: list[InventoryItem] | None = Field(None, alias="inventory-items")
    comments: str | None = ""

    @root_validator
    def temp_fix(cls, values):
        # Temp workaround until https://github.com/netbox-community/devicetype-library/pull/1176 gets merged
        if values["slug"] == "ws-c3750g-12s-e":
            values["model"] = "Catalyst 3750G-12S-E"
        if values["slug"] == "ws-c3750g-12s-s":
            values["model"] = "Catalyst 3750G-12S-S"
        return values

    @root_validator
    def validate_subdevice_role(cls, values):
        if values["subdevice_role"] != "parent" and values["device_bays"] and len(values["device_bays"]) > 0:
            # In Nautobot all device types which have device bays must have a subdevice role of parent
            values["subdevice_role"] = "parent"
        return values

    def to_nautobot(self, dt: DeviceType) -> DeviceType:
        """Convert a DeviceTypeYAML object to a DeviceType object."""

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


def iterate_device_type_files(path: Path) -> Iterable[Path]:
    """Iterate over all device type files in the repository."""
    models = list()
    target_manufacturers = settings.PLUGINS_CONFIG["uoft_nautobot"][
        "device_type_manufacturers"
    ]

    for manufacturer in path.iterdir():
        if manufacturer.name in target_manufacturers:
            models.extend(manufacturer.iterdir())

    return models


def load_device_type_from_yaml(model_file: Path):
    with model_file.open() as f:
        data = yaml.safe_load(f)

    return DeviceTypeYAML(**data)


def update_device_type_from_yaml(dt: DeviceType, dty: DeviceTypeYAML):
    """Update a DeviceType object from a DeviceTypeYAML object."""
    dt.model = dty.model
    dt.slug = dty.slug
    dt.part_number = dty.part_number or ""
    dt.u_height = dty.u_height if dty.u_height is not None else 1
    dt.is_full_depth = dty.is_full_depth or False
    dt.subdevice_role = dty.subdevice_role or ""
    dt.comments = dty.comments or ""
    dty.to_nautobot(dt)



def create_device_type_from_yaml(dty: DeviceTypeYAML):
    mfg, _ = Manufacturer.objects.get_or_create(name=dty.manufacturer)
    dt = DeviceType.objects.create(
        manufacturer=mfg,
        slug=dty.slug,
        model=dty.model,
        part_number=dty.part_number,
        u_height=dty.u_height,
        is_full_depth=dty.is_full_depth,
        subdevice_role=dty.subdevice_role,
        comments=dty.comments,
    )
    dty.to_nautobot(dt)

def update_device_types():
    repo_name = "devicetype-library"
    url = "https://github.com/alextremblay/devicetype-library"
    request = NautobotFakeRequest(
        {
            "user": User.objects.get(username='trembl94'),
            "path": "/extras/git-repositories/",
            "META": {"REMOTE_ADDR": ""},
            "GET": {},
            "POST": {},
        }
    )
    repo, _ = GitRepository.objects.update_or_create(name=repo_name, defaults=dict(request=request, branch="master", remote_url=url, provided_contents=["nautobot.device_types"]))

    ensure_git_repository(repo, MagicMock())
    filesystem_path = repo.filesystem_path
    git_repo_path = Path(filesystem_path)
    dt_path = git_repo_path / "device-types"

    progress = Progress(*Progress.get_default_columns(), MofNCompleteColumn())

    with progress:
        dt_from_yaml = []
        for model_file in progress.track(iterate_device_type_files(dt_path), description="Loading device types from YAML files..."):
            dt_from_yaml.append(load_device_type_from_yaml(model_file))

        dt_from_db: list[DeviceType] = list(
            DeviceType.objects.prefetch_related(
                "consoleporttemplates",
                "consoleserverporttemplates",
                "powerporttemplates",
                "poweroutlettemplates",
                "interfacetemplates",
                "rearporttemplates",
                "frontporttemplates",
                "devicebaytemplates",
            ).all()
        )
        device_types_by_slug = {dt.slug: dt for dt in dt_from_db}
        device_types_by_model = {dt.model: dt for dt in dt_from_db}

        to_update = list()
        to_create = list()

        for dty in dt_from_yaml:
            if dty.slug in device_types_by_slug:
                dt = device_types_by_slug[dty.slug]
                to_update.append((dt, dty))
            elif dty.model in device_types_by_model:
                dt = device_types_by_model[dty.model]
                to_update.append((dt, dty))

            else:
                to_create.append(dty)

        for dt, dty in progress.track(to_update, description="Updating existing device types..."):
            update_device_type_from_yaml(dt, dty)

        for dty in progress.track(to_create, description="Creating new device types..."):
            create_device_type_from_yaml(dty)


class Command(BaseCommand):
    help = "Create or update DeviceType entries in the database, from a 'netbox-community/devicetype-library' compatible git repo"

    def handle(self, *args, **options):
        

        update_device_types()
