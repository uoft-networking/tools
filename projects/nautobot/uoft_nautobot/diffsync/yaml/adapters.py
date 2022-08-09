from pathlib import Path

from nautobot_ssot.jobs import DataSource
from nautobot_ssot.models import Sync
from diffsync import DiffSync
from html_table_parser.parser import HTMLTableParser
from nautobot.ipam.models import RIR, Aggregate

from .models import RIRModel, AggregateModel


class YAML(DiffSync): # pylint: disable=missing-class-docstring

    rir = RIRModel
    aggregate = AggregateModel

    top_level = ['rir', 'aggregate']

    def __init__(self, job: DataSource, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        assert isinstance(job.sync, Sync)
        self.sync = job.sync
        self.load()


    def _process_table(self, table, rir_obj) -> None:
        self.job.log_debug(message="Parsing aggregates from HTML table in YAML file")
        for row in table:
            name, ipv4, ipv6, _, _ = row
            prefixes = []
            if ipv4:
                prefixes.append(ipv4)
            if ipv6:
                prefixes.append(ipv6)
            for prefix in prefixes:
                if prefix in ['10.192.67.64/27']:
                    continue
                aggregate = self.aggregate(
                    prefix=prefix.lower(), description=name, rir_name=rir_obj["name"]
                )
                self.add(aggregate)


    def load(self):
        """Load data from YAML files"""
        data = self.job.load_yaml("test.yaml")
        self.job.log_debug(message=f"Loading data from {Path('test.yaml').resolve()}")
        for rir_obj in data["rirs"]:
            rir = self.rir(
                name=rir_obj["name"],
                slug=rir_obj["slug"],
                description=rir_obj["description"],
                is_private=rir_obj["is_private"],
            )
            self.add(rir)
            if aggregates := rir_obj.get("aggregates"):
                for aggregate_obj in aggregates:
                    aggregate = self.aggregate(
                        prefix=aggregate_obj["prefix"].lower(),
                        description=aggregate_obj["description"],
                        rir_name=rir_obj["name"],
                    )
                    self.add(aggregate)
            if html_table := rir_obj.get("html_table"):
                parser = HTMLTableParser()
                parser.feed(html_table)
                table = parser.tables[0][1:]
                self._process_table(table, rir_obj)                
                        

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