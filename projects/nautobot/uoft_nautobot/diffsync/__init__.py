

from nautobot.extras.jobs import Job
from nautobot_ssot.jobs import DataSource
from diffsync.enum import DiffSyncFlags

from . import bluecat, yaml

name = "Single Source Of Truth"

class FromBluecat(DataSource, Job):
    """Data source for Bluecat DDI data"""

    data_source = "Bluecat" # type: ignore

    def __init__(self):
        super().__init__()
        self.diffsync_flags = self.diffsync_flags | DiffSyncFlags.SKIP_UNMATCHED_DST

    class Meta: # pylint: disable=missing-class-docstring
        name = "Bluecat --> Nautobot"
        description = "Sync data from Bluecat API"

    def load_source_adapter(self):
        self.source_adapter = bluecat.adapters.Bluecat(job=self)

    def load_target_adapter(self):
        self.target_adapter = bluecat.adapters.Nautobot(job=self)

class FromYAML(DataSource, Job):
    """Data source for YAML files"""

    class Meta: # pylint: disable=missing-class-docstring
        name = "From-YAML"
        description = "Sync data from YAML file"

    def load_source_adapter(self):
        self.source_adapter = yaml.adapters.YAML(job=self)

    def load_target_adapter(self):
        self.target_adapter = yaml.adapters.Nautobot(job=self)
