# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Definition of DNS Edge as a target instance."""
from ...http_client.instance import Instance

__all__ = [
    "EdgeInstance",
]


class EdgeInstance(Instance):
    """
    Definition of DNS Edge as a target instance.

    .. versionadded:: 20.6.1
    """

    def parse_url(self):
        """
        Process the service's URL and construct the value of the base URL of
        the service's API.
        """
        self.api_url_base = self.url._replace(path="/")
