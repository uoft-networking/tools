# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Structures and functionality related to describing an HTTP client's target instance."""
import urllib3
import logging


__all__ = [
    "Instance",
]

_DEFAULT_SCHEME = "https"


class Instance:
    """
    Definition of a service instance that can be used as a target by a client.

    :param url: URL of the service.
    :type url: str
    :param logger: Logger to be used for logging. This value is currently not
        utilized.
    :type logger: logging.Logger

    :ivar url: URL of the service.
    :vartype url: Url
    :ivar api_url_base: URL to be used as a base for constructing paths to the
        service's endpoints.
    :vartype api_url_base: Url

    .. versionadded:: 20.6.1
    """

    def __init__(self, url: str, logger: logging.Logger = None):
        # pylint: disable=unused-private-member
        self.__logger = logger if logger else logging.getLogger(__name__)
        self.url = urllib3.util.url.parse_url(url)
        self.url = self.url._replace(
            scheme=self.url.scheme if self.url.scheme else _DEFAULT_SCHEME,
            host=self.url.host if self.url.host else "localhost",
            query=None,
            fragment=None,
        )
        self.api_url_base = self.url
        self.parse_url()

    def parse_url(self):
        """
        Process the service's URL and construct the value of the base URL of
        the service's API.
        """
