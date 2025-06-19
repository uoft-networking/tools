from typing import Literal, Optional, TYPE_CHECKING
from uuid import UUID

from diffsync import DiffSyncModel

from nautobot.ipam.models import Prefix, IPAddress
from nautobot.extras.models import Status

if TYPE_CHECKING:
    from .adapters import Nautobot


class Network(DiffSyncModel):
    """
    Shared data model representing
    what Bluecat calls an IP Block or IP Network,
    and nautobot calls a Prefix.
    """

    # Metadata about this model
    _modelname = "network"
    _identifiers = ("prefix",)
    _attributes = ("name", "status")

    # Data type declarations for all identifiers and attributes

    prefix: str
    name: str
    status: Literal["Active", "Reserved", "Deprecated", "Container"]
    pk: Optional[UUID] = None


class BluecatNetwork(Network):
    """Data model representing an IPv4Block or IPv6Block in Bluecat."""


class NautobotNetwork(Network):
    """Data model representing a container Prefix in nautobot"""

    @classmethod
    def create(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, diffsync: "Nautobot", ids: dict, attrs: dict
    ) -> Optional["DiffSyncModel"]:
        """Create Prefix object in Nautobot."""
        status = Status.objects.get(name=attrs["status"])
        prefix = Prefix(
            prefix=ids["prefix"],
            status=status,
            description=attrs["name"],
        )
        prefix.validated_save()
        return super().create(ids=ids, diffsync=diffsync, attrs=attrs)

    def update(self, attrs: dict) -> Optional["DiffSyncModel"]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Update Prefix object in Nautobot."""
        prefix = Prefix.objects.get(pk=self.pk)  # type: ignore
        if attrs.get("name"):
            prefix.description = attrs["name"]
        if attrs.get("status"):
            prefix.status = Status.objects.get(name=attrs["status"])
        prefix.validated_save()
        return super().update(attrs)

    # def delete(self) -> Optional["DiffSyncModel"]:
    #     """Delete Prefix object in Nautobot."""
    #     if self.diffsync and self.diffsync.job:
    #         self.diffsync.job.log_warning(f"Prefix {self.prefix} will be deleted.")
    #     prefix = Prefix.objects.get(prefix=self.prefix)
    #     prefix.delete()
    #     return super().delete()


class Address(DiffSyncModel):
    """
    Shared data model representing
    what Bluecat calls an IP Address,
    and nautobot calls an IPAddress.
    """

    # Metadata about this model
    _modelname = "address"
    _identifiers = ("address",)
    _attributes = ("name", "status")

    # Data type declarations for all identifiers and attributes

    address: str
    name: str | None
    status: Literal["Active", "Reserved", "Deprecated", "DHCP"]
    pk: Optional[UUID] = None
    bluecat_id: Optional[int] = None


class BluecatAddress(Address):
    """Data model representing an IPv4Address or IPv6Address in Bluecat."""


class NautobotAddress(Address):
    """Data model representing an IPAddress in nautobot"""

    @classmethod
    def create(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, diffsync: "Nautobot", ids: dict, attrs: dict
    ) -> Optional["DiffSyncModel"]:
        """Create IPAddress object in Nautobot."""
        status = Status.objects.get(name=attrs["status"])
        address = IPAddress(
            address=ids["address"],
            status=status,
            description=attrs["name"],
        )
        address.validated_save()
        return super().create(ids=ids, diffsync=diffsync, attrs=attrs)

    def update(self, attrs: dict) -> Optional["DiffSyncModel"]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Update IPAddress object in Nautobot."""
        address = IPAddress.objects.get(pk=self.pk)  # type: ignore
        if attrs.get("name"):
            address.description = attrs["name"]
        if attrs.get("status"):
            address.status = Status.objects.get(name=attrs["status"])
        address.validated_save()
        return super().update(attrs)

    # def delete(self) -> Optional["DiffSyncModel"]:
    #     """Delete IPAddress object in Nautobot."""
    #     if self.diffsync and self.diffsync.job:
    #         self.diffsync.job.log_warning(f"IPAddress {self.address} will be deleted.")
    #     address = IPAddress.objects.get(address=self.address)
    #     address.delete()
    #     return super().delete()
