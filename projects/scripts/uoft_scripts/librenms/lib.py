import threading
import logging

import uoft_librenms

from .._sync import DatasetName, SyncManager, Target, SyncData, DeviceModel, NautobotTarget

logger = logging.getLogger(__name__)


class LibreNMSTarget(Target):
    name = "librenms"

    def __init__(self) -> None:
        super().__init__()
        settings = uoft_librenms.Settings.from_cache()
        self.url = settings.url
        self.token = settings.token

        # used to store thread-local copies of the api object
        self._local_ns = threading.local()

    @property
    def api(self):
        # get a thread-local copy of the api object
        if not hasattr(self._local_ns, "api"):
            self._local_ns.api = uoft_librenms.LibreNMSRESTAPI(self.url, token=self.token.get_secret_value())
        return self._local_ns.api

    def load_data(self, datasets: set):
        assert datasets == {"devices"}, "Only devices are supported"
        logger.info("Loading data from LibreNMS")
        raw_devices = self.api.devices.list_devices(order_type="all")["devices"]
        devices = {}
        local_ids = {}

        logger.info("Processing devices")
        for d in raw_devices:
            # hostnames in librenms are FQDNs, we only care about the actual hostname, the first segment of the FQDN
            hostname = d["hostname"].split(".")[0]
            local_ids[hostname] = d["device_id"]
            devices[hostname] = DeviceModel(hostname=hostname, ip_address=d["ip"])

        self.syncdata = SyncData(
            local_ids=local_ids,
            devices=devices,
            prefixes=None,
            addresses=None,
        )



def get_devices(dev: bool = False):
    from uoft_core import Timeit

    t = Timeit()


    # load data into the sync manager
    datasets: set[DatasetName] = {"devices"}
    sm = SyncManager(LibreNMSTarget(), NautobotTarget(dev), datasets, on_orphan="skip")
    sm.load()

    # synchronize data
    sm.synchronize()

    # commit data
    sm.commit()
    logger.info(f"Time taken: {t.stop().str} seconds")
