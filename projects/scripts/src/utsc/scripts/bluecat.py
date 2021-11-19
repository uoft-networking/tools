from . import config

from BlueCatAPIClient import Client


def collect():
    client = Client()
    res = client.connect(
        url=config.data.bluecat.url,
        username=config.data.bluecat.username,
        password=config.data.bluecat.password,
    )
    print()
