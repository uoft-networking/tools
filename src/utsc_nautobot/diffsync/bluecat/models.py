from glob import glob
from typing import Literal, Optional, Mapping, TYPE_CHECKING
from enum import Enum
from uuid import UUID

from diffsync import DiffSync, DiffSyncModel

from nautobot.ipam.models import Prefix, Status
from nautobot.extras.models import CustomField
from django.contrib.contenttypes.models import ContentType

if TYPE_CHECKING:
    from .adapters import Bluecat, Nautobot

STATUSES = None
def get_statuses():
    global STATUSES
    if STATUSES:
        return STATUSES
    STATUSES = {
        "active": Status.objects.get(slug="active"),
        "reserved": Status.objects.get(slug="reserved"),
        "deprecated": Status.objects.get(slug="deprecated"),
        "container": Status.objects.get(slug="container"),
    }
    return STATUSES

BLUECAT_ID_CUSTOM_FIELD_INITIALIZED = False

def ensure_bluecat_id_cf_exists():
    global BLUECAT_ID_CUSTOM_FIELD_INITIALIZED
    if BLUECAT_ID_CUSTOM_FIELD_INITIALIZED:
        return
    cf = CustomField.objects.get_or_create(
        name="bluecat_id",
        defaults={
            "label": "Bluecat ID",
            "type": "integer",
            "description": "The Object ID Bluecat uses to reference this prefix",
        },
    )[0]
    cf.content_types.add(*ContentType.objects.filter(model__in=['prefix', 'ipaddress']))
    cf.validated_save()
    BLUECAT_ID_CUSTOM_FIELD_INITIALIZED = True

class Network(DiffSyncModel):
    """
    Shared data model representing
    what Bluecat calls an IP Block or IP Network,
    and nautobot calls a Prefix.
    """

    # Metadata about this model
    _modelname = "network"
    _identifiers = ("id",)
    _attributes = ("name","prefix", "status")

    # Data type declarations for all identifiers and attributes

    id: int
    prefix: str
    name: str
    status: Literal['active', 'reserved', 'deprecated', 'container']
    pk: Optional[UUID] = None


class BluecatNetwork(Network):
    """Data model representing an IPv4Block or IPv6Block in Bluecat."""


class NautobotNetwork(Network):
    """Data model representing a container Prefix in nautobot"""

    @classmethod
    def create(
        cls, diffsync: "Nautobot", ids: Mapping, attrs: Mapping
    ) -> Optional["DiffSyncModel"]:
        """Create Prefix object in Nautobot."""
        status = get_statuses()[attrs["status"]]
        prefix = Prefix(
            prefix=attrs["prefix"],
            status=status,
            description=attrs["name"],
        )
        ensure_bluecat_id_cf_exists()
        prefix.custom_field_data['bluecat_id'] = ids["id"]
        prefix.validated_save()
        return super().create(ids=ids, diffsync=diffsync, attrs=attrs)

    def update(self, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Update Prefix object in Nautobot."""
        prefix = Prefix.objects.get(pk=self.pk)  # type: ignore
        if attrs.get("description"):
            prefix.description = attrs["name"]
        if attrs.get("status"):
            prefix.status = get_statuses()[attrs["status"]]
        if attrs.get("prefix"):
            prefix.prefix = attrs["prefix"]
        prefix.validated_save()
        return super().update(attrs)

    def delete(self) -> Optional["DiffSyncModel"]:
        """Delete Prefix object in Nautobot."""
        if self.diffsync and self.diffsync.job:
            self.diffsync.job.log_warning(f"Prefix {self.prefix} will be deleted.")
        prefix = Prefix.objects.get(prefix=self.prefix)
        prefix.delete()
        return super().delete()
