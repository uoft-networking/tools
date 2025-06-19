import re
from . import Settings
from typing import Iterable, Sequence, Literal
from functools import cached_property

from uoft_core.types import BaseModel
from uoft_core.console import console
from pydantic.v1 import validator


class AP(BaseModel):
    name: str
    group: str
    mac_address: str

    @validator("mac_address")
    def validate_mac_address(cls, v):
        mac_address_validate_pattern = re.compile(
            r"^(?:[0-9A-Fa-f]{2}[:\-\.]?){5}(?:[0-9A-Fa-f]{2})$"
        )
        match = re.match(mac_address_validate_pattern, v)
        if match:
            v = re.sub("[:.-]", "", v)
            v = ":".join([v[i : i + 2] for i in range(0, 12, 2)])
            v = v.lower()
            return v
        else:
            raise ValueError("Invalid MAC Address")

    @validator("name", "group")
    def validate_len(cls, v):
        if len(v) > 75:
            raise ValueError("too long, must be 75 characters or less")
        return v


class ProvisionError(Exception):
    def __init__(self, *args: object, ap: AP) -> None:
        self.ap = ap
        super().__init__(*args)


class InvalidField(ProvisionError):
    def __init__(self, *args: object, field: str, ap: AP) -> None:
        self.field = field
        super().__init__(*args, ap=ap)


class AlreadyExists(ProvisionError):
    def __init__(self, *args: object, ap: AP, old_ap: dict[str, str]) -> None:
        self.old_ap = old_ap
        super().__init__(*args, ap=ap)


class Provisioner:
    def __init__(
        self,
        on_error: Literal["skip", "stop", "force"] = "skip",
        dry_run: bool = False,
    ) -> None:
        self.settings = Settings.from_cache()
        self.error_policy = on_error
        self.dry_run = dry_run
        self._controller = None
        self._mobility_master = None

    def provision_aps(
        self,
        inputs: Sequence[tuple[str, str, str]],
    ):
        return list(self.provision_aps_iter(inputs))

    def provision_aps_iter(
        self,
        inputs: Iterable[tuple[str, str, str]],
    ):
        for ap in inputs:
            try:
                yield self.provision_ap(*ap)
            except InvalidField as e:
                if self.error_policy == "skip":
                    console().print(
                        f"[red]ERROR[/] {e.args[0]} [red]SKIPPING[/] {e.ap}"
                    )
                    yield e
                else:
                    raise e
            except AlreadyExists as e:
                if "already correctly provisioned" in e.args[0]:
                    console().print(
                        f"AP_NAME {e.ap.name} already correctly provisioned. [green]SKIPPING[/]"
                    )
                    yield e.ap
                elif self.error_policy == "force":
                    yield self.force_provision_ap(e.ap, e.old_ap)
                elif self.error_policy == "skip":
                    console().print(
                        f"[red]ERROR[/] {e.args[0]} [red]SKIPPING[/] {e.ap}"
                    )
                    yield e
                else:
                    raise e

    def deprovision_aps(self, inputs: Sequence[tuple[str, str, str]]):
        return list(self.deprovision_aps_iter(inputs))
    
    def deprovision_aps_iter(self, inputs: Iterable[tuple[str, str, str]]):
        for ap in inputs:
            try:
                ap_dict = {"AP-Name": ap[0], "MAC-Address": ap[2]}
                yield self.delete_existing_ap(ap_dict)
            except ProvisionError as e:
                if self.error_policy == "skip":
                    console().print(
                        f"[red]ERROR[/] {e.args[0]} [red]SKIPPING[/] {e.ap}"
                    )
                    yield e
                else:
                    raise e

    def force_provision_ap(self, ap: AP, old_ap: dict[str, str]):
        self.delete_existing_ap(old_ap)
        return self.provision_ap(ap.name, group=ap.group, mac_address=ap.mac_address)

    def delete_existing_ap(self, old_ap):
        msg = f"Deleted existing AP_NAME {old_ap['AP-Name']} / {old_ap['MAC-Address']} from allowlist...[green]GOOD[/]"
        if self.dry_run:
            msg = "Would have " + msg
        else:
            self.mobility_master.ap_provisioning.wdb_cpsec_delete_mac(
                old_ap["MAC-Address"]
            )
            try:
                del self.existing_aps_by_mac
            except AttributeError:
                pass
            try:
                del self.existing_aps_by_name
            except AttributeError:
                pass
            try:
                del self.existing_aps_in_allowlist
            except AttributeError:
                pass
        console().print(msg)

    def provision_ap(self, name, group, mac_address):
        console().print(
            f"Provisioning {name} with MAC {mac_address} in group {group}..."
        )

        # instantiating the AP will validate the fields automatically. Thanks Pydantic!
        ap = AP(mac_address=mac_address, group=group, name=name)
        console().print("Verifying input parameters...[green]GOOD[/]")

        self._validate_group(ap)

        self._validate_name(ap)

        self._validate_mac(ap)

        msg = f"Added new AP_NAME {ap.name} / {ap.mac_address} to allowlist...[green]GOOD[/]"
        if self.dry_run:
            msg = "Would have " + msg
        else:
            self.mobility_master.ap_provisioning.wdb_cpsec_add_mac(
                ap.mac_address, ap.group, ap.name
            )
        console().print(msg)

        msg = f"Modified CPSEC entry for {ap.name} / {ap.mac_address} to factory_approved...[green]GOOD[/]"
        if self.dry_run:
            msg = "Would have " + msg
        else:
            self.mobility_master.ap_provisioning.wdb_cpsec_modify_mac_factory_approved(
                ap.mac_address
            )
        console().print(msg)

        return ap

    def __del__(self):
        # Make sure we log out of the controllers when we're done
        if self._controller is not None:
            self._controller.logout()
        if self._mobility_master is not None:
            self._mobility_master.logout()

    @property
    def controller(self):
        if self._controller is None:
            # we only need API access to a controller to collect the list of AP groups
            # it doesn't really matter which controller we use, so we just pick the first one
            self._controller = self.settings.md_api_connections[0]
            self._controller.login()
        return self._controller

    @property
    def mobility_master(self):
        if self._mobility_master is None:
            self._mobility_master = self.settings.mm_api_connection
            self._mobility_master.login()
        return self._mobility_master

    def _validate_group(self, ap: AP):
        if ap.group not in self.all_groups_by_name:
            msg = f"AP_GROUP {ap.group} does not exist on controller."
            raise InvalidField(msg, field="ap_group", ap=ap)
        console().print(
            f"Verifying AP_GROUP {ap.group} exists on controller...[green]GOOD[/]"
        )

    def _validate_name(self, ap: AP):
        if ap.name in self.existing_aps_by_name:
            existing_ap = self.existing_aps_by_name[ap.name]
            if existing_ap["MAC-Address"] == ap.mac_address:
                if existing_ap["AP-Group"] == ap.group:
                    raise AlreadyExists(
                        f"AP_NAME {ap.name} is already correctly provisioned.",
                        ap=ap,
                        old_ap=existing_ap,
                    )
                else:
                    msg = f"AP_NAME {ap.name} already exists on controller in group {existing_ap['AP-Group']}."
                    raise AlreadyExists(msg, ap=ap, old_ap=existing_ap)
            else:
                msg = f"AP_NAME {ap.name} already exists on controller with MAC {existing_ap['MAC-Address']}."
                raise AlreadyExists(msg, ap=ap, old_ap=existing_ap)
        console().print(
            f"Verifying AP_NAME {ap.name} is not in use...[green]GOOD[/]"
        )

    def _validate_mac(self, ap: AP):
        if ap.mac_address in self.existing_aps_by_mac:
            existing_ap = self.existing_aps_by_mac[ap.mac_address]
            if existing_ap["AP-Name"] == ap.name:
                if existing_ap["AP-Group"] == ap.group:
                    raise AlreadyExists(
                        f"MAC {ap.mac_address} is already correctly provisioned.",
                        ap=ap,
                        old_ap=existing_ap,
                    )
                else:
                    msg = f"MAC {ap.mac_address} already exists on controller in group {existing_ap['AP-Group']}."
                    raise AlreadyExists(msg, ap=ap, old_ap=existing_ap)
            msg = f"MAC {ap.mac_address} already exists on controller with AP_NAME {existing_ap['AP-Name']}."
            raise AlreadyExists(msg, ap=ap, old_ap=existing_ap)
        console().print(
            f"Verifying MAC {ap.mac_address} is not in use...[green]GOOD[/]"
        )

    @cached_property
    def all_groups_by_name(self) -> set[str]:
        return {
            g["profile-name"].rpartition("'")[2]
            for g in self.controller.wlan.get_ap_groups()
        }

    @cached_property
    def existing_aps_in_allowlist(self):
        return self.mobility_master.ap_provisioning.get_cpsec_allowlist()

    @cached_property
    def existing_aps_by_name(self):
        return {
            ap["AP-Name"]: ap for ap in self.existing_aps_in_allowlist if ap["AP-Name"]
        }

    @cached_property
    def existing_aps_by_mac(self):
        return {
            ap["MAC-Address"]: ap
            for ap in self.existing_aps_in_allowlist
            if ap["MAC-Address"]
        }
