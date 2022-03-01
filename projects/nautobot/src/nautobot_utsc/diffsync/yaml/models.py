from typing import Optional, Mapping

from diffsync import DiffSync, DiffSyncModel

from nautobot.ipam.models import RIR, Aggregate


class RIRModel(DiffSyncModel):
    """Shared data model representing a RIR (internet registry) entry"""

    # Metadata about this model
    _modelname = "rir"
    _identifiers = ("name",)
    _attributes = ("slug", "description", "is_private")

    # Data type declarations for all identifiers and attributes
    name: str
    slug: str
    description: str
    is_private: bool

    # This model implements create/update/delete methods for nautobot,
    # since it's used only in a one-way sync TO nautobot.
    # If this were a two-way sync job, we would need to implement subclasses
    # of this model instead for each data target.
    @classmethod
    def create(
        cls, diffsync: "DiffSync", ids: Mapping, attrs: Mapping
    ) -> Optional["DiffSyncModel"]:
        """Create a new RIR in nautobot's DB from the given data."""
        rir = RIR(
            name=ids['name'],
            slug=attrs['slug'],
            description=attrs['description'],
            is_private=attrs['is_private'],
        )
        rir.validated_save()
        return super().create(diffsync, ids, attrs)

    def update(self, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Update an existing RIR in nautobot's DB from the given data."""
        rir = RIR.objects.get(name=self.name)
        for attr_name in attrs:
            setattr(rir, attr_name, attrs[attr_name])
        rir.validated_save()
        return super().update(attrs)

    def delete(self) -> Optional["DiffSyncModel"]:
        """Delete an existing RIR in nautobot's DB."""
        rir = RIR.objects.get(name=self.name)
        rir.delete()
        return super().delete()


class AggregateModel(DiffSyncModel):
    """Shared data model representing an aggregate"""

    # Metadata about this model
    _modelname = "aggregate"
    _identifiers = ("prefix",)
    _attributes = ("description", "rir_name")

    # Data type declarations for all identifiers and attributes
    prefix: str
    description: str
    rir_name: str

    # This model implements create/update/delete methods for nautobot,
    # since it's used only in a one-way sync TO nautobot.
    # If this were a two-way sync job, we would need to implement subclasses
    # of this model instead for each data target.
    @classmethod
    def create(
        cls, diffsync: "DiffSync", ids: Mapping, attrs: Mapping
    ) -> Optional["DiffSyncModel"]:
        """Create a new Aggregate in nautobot's DB from the given data."""
        aggregate = Aggregate(
            prefix=ids['prefix'],
            description=attrs['description'],
            rir=RIR.objects.get(name=attrs['rir_name']),
        )
        aggregate.validated_save()
        return super().create(diffsync, ids, attrs)

    def update(self, attrs: Mapping) -> Optional["DiffSyncModel"]:
        """Update an existing Aggregate in nautobot's DB from the given data."""
        aggregate = Aggregate.objects.get(prefix=self.prefix)
        for attr_name in attrs:
            if attr_name == 'rir_name':
                setattr(aggregate, 'rir', RIR.objects.get(name=attrs[attr_name]))
            else:
                setattr(aggregate, attr_name, attrs[attr_name])
        aggregate.validated_save()
        return super().update(attrs)

    def delete(self) -> Optional["DiffSyncModel"]:
        """Delete an existing Aggregate in nautobot's DB."""
        aggregate = Aggregate.objects.get(prefix=self.prefix)
        aggregate.delete()
        return super().delete()
