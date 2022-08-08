# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Provisional backward compatible version of prior client for to BlueCat Address Manager REST API.

.. versionadded:: 20.12.1
"""
from ..auto import _wadl_parser
from ..auto.client import _get_rest_service_base_url
from .rest_dict import RESTDict
from .rest_entity_array import RESTEntityArray
from .rest_fault import RESTFault
from .....http_client import GeneralError, ErrorResponse
import requests


class ProvisionalClient:
    """
    A client to BlueCat Address Manager REST API. It is to be used during
    the transitional period while we migrate away from the `SOAP` and
    `suds`-influenced legacy designs.

    .. versionadded:: 20.12.1

    .. versionchanged:: 21.5.1
        The initializer of the class no longer takes in a ``url`` and ``kwargs``, but an instance
        of a raw client.
    """

    def __init__(self, raw_client):
        self._raw_client = raw_client

    def login(self, username, password):
        """
        Wrapper for the REST login API/endpoint.

        :param username: Username of the user that logs in.
        :type username: str
        :param password: Password of the user that logs in.
        :type password: str
        :return: Access token for BlueCat Address Manager.
        :rtype: str
        """
        try:
            return self._raw_client.login(username, password)
        except ErrorResponse as exc:
            raise RESTFault(exc.response.text, exc.response) from exc
        except GeneralError as exc:
            raise RESTFault(str(exc)) from exc

    def loginWithOptions(self, username, password, options):
        """
        Wrapper for the REST login API/endpoint.

        :param username: Username of the user that logs in.
        :type username: str
        :param password: Password of the user that logs in.
        :type password: str
        :param options: Login options.
        :type options: str
        :return: Access token for BlueCat Address Manager.
        :rtype: str
        """
        try:
            return self._raw_client.loginWithOptions(username, password, options)
        except ErrorResponse as e:
            raise RESTFault(e.response.text, e.response) from e
        except GeneralError as e:
            raise RESTFault(str(e)) from e

    @classmethod
    def process_url(cls, url, **kwargs):  # pylint: disable=unused-argument
        """
        Returns the base URL to the BAM's REST API service based on an URL to a BAM server.

        :param url: URL to a BAM server.
        :type url: str
        :param kwargs: Various options.
        :type kwargs: dict
        :return: The URL to the base path for the REST service of BAM.
        :rtype: str

        .. note::

           This is a provisionally provided method to ensure backward compatibility. It will be
           deprecated and removed in a future release.

        .. versionadded:: 20.12.1
        """
        # NOTE: Delay raising deprecation warning until Gateway's own code will not trigger it.
        # warnings.warn(
        #     "Class method 'Client.process_url' has been deprecated in favour of"
        #     " function 'bluecat_libraries.address_manager.api.rest.auto.get_rest_service_base_url'."
        #     " Be advised that the parameters have changed.",
        #     DeprecationWarning)
        return _get_rest_service_base_url(url, use_https=url.startswith("https"))

    @property
    def service(self) -> object:
        """
        Provides access to the internal service with automatically generated methods for the
        endpoints of the BAM REST API.

        .. note::

           This is a provisionally provided property to ensure backward compatibility. It will be
           deprecated and removed in a future release.

        .. versionadded:: 20.12.1
        """
        # NOTE: Delay raising deprecation warning until Gateway's own code will not trigger it.
        # warnings.warn(
        #     "Member 'service' has been deprecated and will be removed in a future release."
        #     " You may now use the instance of 'Client' directly the same way you would have used 'service'.",
        #     DeprecationWarning)
        return self

    @property
    def session(self) -> requests.Session:
        """
        Provides access to the internal Session instance used for HTTP communication.

        .. note::

           This is a provisionally provided property to ensure backward compatibility. It will be
           deprecated and removed in a future release.

        .. versionadded:: 21.5.1
        """
        return self._raw_client.session

    @property
    def url(self) -> str:
        """
        Provides the base URL of the endpoints of the BAM REST API service.

        .. note::

           This is a provisionally provided property to ensure backward compatibility. It will be
           deprecated and removed in a future release.

        .. versionadded:: 20.12.1
        """
        # NOTE: Delay raising deprecation warning until Gateway's own code will not trigger it.
        # warnings.warn(
        #     "Member 'url' has been deprecated and will be removed in a future release."
        #     " It is available for a limited transitional period.",
        #     DeprecationWarning)
        return self._service.url.rstrip("/")

    @classmethod
    def _get_namespace(cls, element):
        # NOTE: Delay raising deprecation warning until Gateway's own code will not trigger it.
        # warnings.warn(
        #     "Class method '_get_namespace' has been deprecated in favour of"
        #     " function 'bluecat_libraries.address_manager.api.rest.auto.wadl_parser.get_element_namespace'.",
        #     DeprecationWarning)
        return _wadl_parser.get_element_namespace(element)

    def __getattr__(self, item):
        # Obtain the actual method from the parent class. Then capture its
        # output or exceptions and wrap them in the currently expected envelopes
        # for result or error.
        func = getattr(self._raw_client, item)

        def func_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, list):
                    return RESTEntityArray(result)
                if isinstance(result, dict):
                    return RESTDict(result)
                return result
            except ErrorResponse as exc:
                raise RESTFault(exc.response.text, exc.response) from exc
            except GeneralError as exc:
                raise RESTFault(str(exc)) from exc

        return func_wrapper
