from nautobot.extras.jobs import Job
from nautobot_ssot.jobs import DataSource

from .adapters import YAML, Nautobot


class SyncFromYAML(DataSource, Job):
    """Data source for YAML files"""

    class Meta: # pylint: disable=missing-class-docstring
        name = "From-YAML"
        description = "Sync data from YAML file"

    def load_source_adapter(self):
        self.source_adapter = YAML(job=self)

    def load_target_adapter(self):
        self.target_adapter = Nautobot(job=self)