# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module for the client to work with BlueCat Service Point API."""

from ...http_client.client import Client
from ...http_client.exceptions import UnexpectedResponse
from .instance import ServicePointInstance


class ServicePointClient(Client):
    """`Client` uses the `requests` library to communicate with Service Point."""

    def __init__(self, url):
        super().__init__(ServicePointInstance(url))

    def get_v1_status_health(self):
        """
        The health probe API validates the status of DNS resolution. Use this method to configure the DNS Edge
         service point behind load balancers.

        Example:

            .. code:: python

                from utsc.core._vendor.bluecat_libraries.service_point.api import ServicePointClient

                client = ServicePointClient(<service_point_url>)
                try:
                    client.get_v1_status_health()
                catch Exception:
                    available = False
                else:
                    available = True

        .. versionadded:: 20.6.1
        """
        response = self.http_get(self._url_for("/v1/status/health"))
        if response.status_code != 200:
            raise UnexpectedResponse(
                "Got {status_code} which is unexpected".format(status_code=response.status_code),
                response,
            )

    def get_v1_status_spdiagnostics(self):
        """
        Use this method for troubleshoot a service point. It returns the overall health status of the service point,
        the service point ID, each service's status and service version, configured forwarder IPs,
        the current local time and time zone, and policy details.

        Example:

            .. code:: python

                from utsc.core._vendor.bluecat_libraries.service_point.api import ServicePointClient

                client = ServicePointClient(<service_point_url>)
                status_spdiagnostics = client.get_v1_status_spdiagnostics()

        .. versionadded:: 20.6.1
        """

        response = self.http_get(self._url_for("/v1/status/spDiagnostics"))
        return response.json()
