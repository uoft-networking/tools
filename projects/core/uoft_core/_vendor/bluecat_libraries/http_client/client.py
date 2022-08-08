# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module for the base client"""

import requests
from requests import codes, Response

from .exceptions import (
    GeneralError,
    ClientError,
    ErrorResponse,
    UnexpectedResponse,
)
from .instance import Instance

__all__ = ["Client"]


class Client:
    """
    An HTTP client with some utilities to make creating service clients easier.
    The class implements the necessary methods to act as a context manager.

    :param target: A definition of a target service.
    :type target: Instance

    .. versionadded:: 20.6.1
    """

    def __init__(self, target: Instance):
        self.session = requests.Session()
        self.target = target
        self.token = None
        self.token_type = None

    def close(self):
        """Release any allocated resources, e.g., an internal session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def is_authenticated(self) -> bool:
        """Determine whether the authentication necessary to communicate with the target service is set."""
        return bool(self.token)

    def _require_auth(self):
        """
        Raise exception if the client does not have the necessary authentication
        set to communicate with the target service.
        """
        if not self.is_authenticated:
            raise ClientError("Use of this method requires authentication, but none is provided.")

    def _url_for(self, name: str) -> str:
        name = name.lstrip("/")
        return self.target.api_url_base.url + name

    def is_error_response(self, response: requests.Response) -> bool:
        """
        Determine whether a response is an error response.

        This method exists to allow derived classes to customize the behaviour.

        :param response: Object representing the HTTP response.
        :type response: requests.Response
        :return: Whether the response conveys an error.
        :rtype: bool
        """
        return not response.ok

    def handle_error_response(self, response: requests.Response):
        """
        Handle a response that's considered to be an error (based on the HTTP
        status code). The standard implementation raises an exception. Derived
        classes may overwrite it to provide custom handling.

        :param response: Object representing the HTTP response.
        :type response: requests.Response
        """
        raise ErrorResponse(
            "Response with HTTP status code {}".format(response.status_code), response
        )

    def http_request(
        self,
        method,
        url,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json=None,
        expected_status_codes=None,
    ):
        """
        Perform an HTTP request based on the provided parameters. It is done
        as part of the internally maintained session, i.e. using the set
        authorization. The majority of the method's parameters correspond to
        their namesakes in :py:meth:`requests.Session.request`. However, this
        class additionally processes the response. It uses
        :py:meth:`is_error_response` and :py:meth:`handle_error_response` to
        detect and handle error responses. That approach allows derived classes
        to customize the behaviour. Additionally, it checks the HTTP status
        code against provided `expected_status_codes` and raises an exception.

        :param method: HTTP method to be used.
        :type method: str
        :param url: URL to be used for the request.
        :type url: str
        :param params: Query parameters to be passed in the request.
        :type params: dict, optional
        :param data: Value to be sent in the body of the request.
        :type data: dict, list[tuple], bytes, or a file-like object, optional
        :param headers: HTTP Headers to be sent with the request.
        :type headers: dict, optional
        :param cookies: Cookies to be sent with the request.
        :type cookies: dict or CookieJar object, optional
        :param files: File-like objects for multipart encoding upload.
        :type files: dict, optional
        :param auth: Object to handle HTTP Authentication.
        :type auth: tuple or callable, optional
        :param timeout: How long to wait to receive data before giving up. If
            given as a tuple, it is used as (connect, read) timeouts.
        :type timeout: float or tuple, optional
        :param allow_redirects: Whether to allow redirects. Defaults to ``True``.
        :type allow_redirects: bool, optional
        :param proxies: Mapping of protocol or protocol and hostname to a URL
            of a proxy to be used.
        :type proxies: dict, optional
        :param hooks: Hooks to be called upon events.
        :type hooks: dict
        :param stream: Whether to immediately read the response content.
            Defaults to ``False``.
        :type stream: bool, optional
        :param verify: Whether to verify the server's TLS certificate. If a
            string is passed, it is treated as a path to a CA bundle to be
            used. Defaults to ``True``.
        :type verify: bool or str
        :param cert: Path to a SSL client certificate file (.pem). If the
            certificate has a key, it can be provides as the second item in a
            tuple, with the first item being the path to the certificate file.
        :type cert: str or tuple, optional
        :param json: Object to be sent as JSON in the body of the request.
        :type json: object, optional
        :param expected_status_codes: HTTP status codes that are acceptable as
            a status code of the HTTP response. If the received code does not
            match the passed values, an :py:exc:`UnexpectedResponse` is raised.
            If left empty, the status code validation is not performed.
        :type expected_status_codes: iterable[int], optional
        :return: Object representing the HTTP response received to the performed
            request.
        :rtype: requests.Response
        """
        try:
            response = self.session.request(
                method,
                url,
                params,
                data,
                headers,
                cookies,
                files,
                auth,
                timeout,
                allow_redirects,
                proxies,
                hooks,
                stream,
                verify,
                cert,
                json,
            )
        except Exception as exc:
            raise GeneralError("Error communicating with target.") from exc

        if self.is_error_response(response):
            self.handle_error_response(response)

        if expected_status_codes and response.status_code not in expected_status_codes:
            raise UnexpectedResponse("Response with unexpected HTTP status code.", response)

        return response

    def http_get(self, url, params=None, expected_status_codes=None, **kwargs) -> Response:
        """
        Perform an HTTP GET request based on the provided parameters. See
        `http_request` for details.

        If `expected_status_codes` is not specified, it defaults to `(200, )`.
        200 is the HTTP status code for successful response `OK`.
        """
        if expected_status_codes is None:
            expected_status_codes = (codes.ok,)
        return self.http_request(
            "GET", url, params, expected_status_codes=expected_status_codes, **kwargs
        )

    def http_post(
        self, url, params=None, data=None, json=None, expected_status_codes=None, **kwargs
    ) -> Response:
        """Perform an HTTP POST request based on the provided parameters. See `http_request` for details."""
        return self.http_request(
            "POST",
            url,
            params,
            data,
            json=json,
            expected_status_codes=expected_status_codes,
            **kwargs,
        )

    def http_put(
        self, url, params=None, data=None, json=None, expected_status_codes=None, **kwargs
    ) -> Response:
        """Perform an HTTP PUT request based on the provided parameters. See `http_request` for details."""
        return self.http_request(
            "PUT",
            url,
            params,
            data,
            json=json,
            expected_status_codes=expected_status_codes,
            **kwargs,
        )

    def http_patch(
        self, url, params=None, data=None, json=None, expected_status_codes=None, **kwargs
    ) -> Response:
        """Perform an HTTP PATCH request based on the provided parameters. See `http_request` for details."""
        return self.http_request(
            "PATCH",
            url,
            params,
            data,
            json=json,
            expected_status_codes=expected_status_codes,
            **kwargs,
        )

    def http_delete(
        self, url, params=None, data=None, json=None, expected_status_codes=None, **kwargs
    ) -> Response:
        """Perform an HTTP DELETE request based on the provided parameters. See `http_request` for details."""
        return self.http_request(
            "DELETE",
            url,
            params,
            data,
            json=json,
            expected_status_codes=expected_status_codes,
            **kwargs,
        )
