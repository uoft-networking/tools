from nautobot.extras.jobs import Job
from nautobot_ssot.jobs import DataSource

from .adapters import Bluecat, Nautobot


class SyncFromBluecat(DataSource, Job):
    """Data source for Bluecat DDI data"""

    class Meta: # pylint: disable=missing-class-docstring
        name = "From-Bluecat"
        description = "Sync data from Bluecat API"

    def load_source_adapter(self):
        self.source_adapter = Bluecat(job=self)

    def load_target_adapter(self):
        self.target_adapter = Nautobot(job=self)