# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Definition of BAM Failover as a target instance."""
from ...http_client.instance import Instance

__all__ = [
    "FailoverAPIInstance",
]


class FailoverAPIInstance(Instance):
    """
    Definition of BAM Failover as a target instance.

    .. versionadded:: 21.3.1
    """

    def parse_url(self):
        """
        Process the service's URL and construct the value of the base URL of
        the service's API.
        """
        # fmt: off
        self.api_url_base = self.url._replace(
            scheme='https',
            port=self.url.port if self.url.port else '8444',
            path='/'
        )
