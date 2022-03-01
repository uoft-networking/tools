from nautobot_ssot.jobs import DataSource
from nautobot_ssot.models import Sync
from diffsync import DiffSync

# from .models import IPv4Block, IPv6Block


class Bluecat(DiffSync): # pylint: disable=missing-class-docstring

    # rir = RIRModel
    # aggregate = AggregateModel

    # top_level = ['rir', 'aggregate']

    def __init__(self, job: DataSource, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        assert isinstance(job.sync, Sync)
        self.sync = job.sync
        self.load()


    def load(self):
        """Load data from Bluecat API"""
        data = self.job.load_yaml("test.yaml")
                      
                        

class Nautobot(DiffSync): # pylint: disable=missing-class-docstring
    
    rir = RIRModel
    aggregate = AggregateModel

    top_level = ['rir', 'aggregate']

    def __init__(self, job: DataSource, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        assert isinstance(job.sync, Sync)
        self.sync = job.sync
        self.load()

    def load(self):
        """Load data from nautobot's DB"""
        for rir in RIR.objects.all():
            rir_model = self.rir(
                name=rir.name,
                slug=rir.slug,
                description=rir.description,
                is_private=rir.is_private,
            )
            self.add(rir_model)
        for aggregate in Aggregate.objects.all():
            aggregate_model = self.aggregate(
                prefix=str(aggregate.prefix),
                description=aggregate.description,
                rir_name=aggregate.rir.name,
            )
            self.add(aggregate_model)