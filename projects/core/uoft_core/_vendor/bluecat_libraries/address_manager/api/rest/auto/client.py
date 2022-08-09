# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Creating the Client object that is the interface for doing API calls.
"""
import logging
import re
import threading
from typing import Any, Optional

from requests import Session
from urllib3.util import parse_url

from .....http_client import GeneralError, ErrorResponse
from . import _wadl_parser
from ...serialization import deserialize_joined_key_value_pairs
from ..._version import Version as _Version

__all__ = [
    "Client",
]

_LOGGER = logging.getLogger(__name__)
_LOGIN_RESPONSE_WITH_TOKEN = re.compile(
    r"Session Token-> (?P<token>.+) <- for User : (?P<username>.+)$",
    # r'^Session Token-> (?P<token>.+) <- for User : (?P<username>.+)$',
    re.UNICODE,
)

_lock = threading.Lock()

_SERVICE_CACHE = {}


def _get_rest_service_base_url(url: str, use_https: bool = False) -> str:
    """
    Takes an URL to a BAM server and returns the base URL to the BAM's REST
    service.

    :param url: A URL to a BlueCat Address Manager. The path, query, and
        fragments portions will be ignored, even if provided
    :type url: str
    :param use_https: Whether the returned URL should be for HTTPS. Defaults
        to `False`.
    :type use_https: bool, Optional

    :return: The URL to the base path for the REST service of BAM.
    :rtype: str
    """
    parts = parse_url(url)
    scheme = "https" if use_https else (parts.scheme or "http")
    if parts.port:
        host_incl_port = "{}:{}".format(parts.host, parts.port)
    else:
        host_incl_port = parts.host
    if not host_incl_port:
        raise GeneralError("Invalid BAM API URL: {url} provided!".format(url=url))
    address = "{scheme}://{host_incl_port}/Services/REST/".format(
        scheme=scheme, host_incl_port=host_incl_port
    )
    return address


def _get_rest_service_wadl_url(rest_service_base_url: str) -> str:
    """
    Return the URL to the WADL of BAM's REST service.

    :param rest_service_base_url: Base URL of BAM's REST service.
    :type rest_service_base_url: str
    :return: The URL to the WADL of BAM's REST service.
    :rtype: str
    """
    return rest_service_base_url + "application.wadl"


def _get_rest_endpoint_base_url(rest_service_base_url: str) -> str:
    """
    Return the base URL of the endpoints of BAM's REST service.

    :param rest_service_base_url: Base URL of BAM's REST service.
    :type rest_service_base_url: str
    :return: The base URL of the endpoints of BAM's REST service.
    :rtype: str
    """
    return (
        rest_service_base_url + "v1"
    )  # TODO: Shouldn't this end in a forward slash?  # pylint: disable=fixme


def _get_service_for_url(rest_service_base_url, session):
    """
    Returns an object with automatically generated methods for the endpoints of the BAM REST API
    service.

    The returned object is cached for the given URL. Subsequent calls with the same URL will return
    the cached object. If there is no cached object satisfies the call, the service description
    of the BAM REST API is obtained and an object is created.

    :param rest_service_base_url: Base URL of the REST service of BAM.
    :type rest_service_base_url: str
    :param session: A session object to be used, if any data needs to be obtained from BAM through
        HTTP requests.
    :type session: requests.Session
    :return: Service
    """
    global _SERVICE_CACHE
    wadl_url = _get_rest_service_wadl_url(rest_service_base_url)
    if wadl_url not in _SERVICE_CACHE:
        try:
            _lock.acquire()

            # A second check, because in the time between the first check and
            # the locking another thread might have already obtained and cached
            # the necessary service.
            if wadl_url in _SERVICE_CACHE:
                return _SERVICE_CACHE[wadl_url]

            wadl = _get_rest_service_wadl(wadl_url, session)
            rest_endpoint_base_url = _get_rest_endpoint_base_url(rest_service_base_url)
            parser = _wadl_parser.WADLParser(rest_endpoint_base_url, wadl)
            _SERVICE_CACHE[wadl_url] = parser.generate_service()
        finally:
            _lock.release()
    return _SERVICE_CACHE[wadl_url]


def _get_rest_service_wadl(wadl_url: str, session: Session, *, logger=None) -> str:
    """
    Returns the WADL specification of a service as text.

    :param wadl_url: URL of the WADL specification of the service.
    :type wadl_url: str
    :param session: A session object to be used to issue HTTP requests to obtain the WADL.
    :type session: requests.Session
    :param logger: Logger for logging messages.
    :type logger: logging.Logger
    :return: A service's WADL as text.
    :rtype: str
    """
    logger = logger if logger else _LOGGER
    try:
        # NOTE: The following line should work. The expectation is that the value of `verify` of
        # the session will be honoured inside the `.get()` call. However, in the test pipeline /
        # environment that does not happen. Until test environment is updated be explicit.
        #
        # response = session.get(wadl_url)
        #
        # NOTE: Passing `verify` explicitly in the method call as a temporary workaround.
        response = session.get(wadl_url, verify=session.verify)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Error obtaining service specification from BAM: {}".format(repr(exc)))
        raise GeneralError(str(exc)) from exc
    if not response.ok:
        message = "Error obtaining service specification from BAM: HTTP {}: {}".format(
            response.status_code, response.reason
        )
        logger.exception(message)
        raise GeneralError(message)
    return response.text


class Client:
    """Client object for handling REST requests."""

    def __init__(self, url: str, *, verify: Any = True) -> None:
        """
        ``verify`` has the same meaning as arguments of the same name commonly found in
        ``requests`` functions.
        """
        self.session = Session()
        self.session.verify = verify
        rest_service_base_url = _get_rest_service_base_url(url, use_https=url.startswith("https"))
        self._service = _get_service_for_url(rest_service_base_url, self.session)

    def close(self):
        """Release any allocated resources, e.g., an internal session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def version(self) -> Optional[str]:
        """
        Version of the BlueCat Address Manager the used service is for. Return value
        ``None`` means this client has never been logged into.

        :return: Version of BlueCat Address Manager.
        :rtype: Optional[str]
        """
        v = self._service.version
        return str(v) if v else None

    @property
    def is_authenticated(self) -> bool:
        """
        Determine whether the authentication necessary to communicate with BlueCat Address
        Manager is set.
        """
        return bool(self.session.headers["Authorization"])

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
            content = self._service.login(self.session, username, password)
        except Exception as exc:  # pylint: disable=broad-except
            if password is not None and password in str(exc):
                raise GeneralError("Connection Error!") from exc
            raise

        match = _LOGIN_RESPONSE_WITH_TOKEN.search(content)
        if not match:
            raise GeneralError(
                "Invalid username or password."
            )  # Keeping the original exception message.
            # raise GeneralError('Invalid response from BAM.')

        token = match.group("token")
        # TODO: Could usernames in BAM be case-insensitive?  # pylint: disable=fixme
        # username_ = match.group('username')
        # if username != username_:
        #     raise GeneralError('Received response for different user.')

        self.set_token(token)
        return token

    def loginWithOptions(self, username, password, options):
        """
        Wrapper for the REST loginWithOptions API/endpoint.

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
            content = self._service.loginWithOptions(self.session, username, password, options)
        except Exception as e:  # pylint: disable=broad-except
            if password is not None and password in str(e):
                raise GeneralError("Connection Error!") from e
            raise

        match = _LOGIN_RESPONSE_WITH_TOKEN.search(content)
        if not match:
            raise GeneralError("Invalid username or password.")

        token = match.group("token")
        self.set_token(token)
        return token

    def set_token(self, token):
        """
        Set token used for BAM authentication.

        :param token: Token to be used for BAM authentication.
        """
        self.session.headers.update({"Authorization": token})
        if not self._service.version:
            self._set_version()

    def clear_token(self):
        """
        Clear the token used for BAM authentication.
        """
        del self.session.headers["Authorization"]

    def _set_version(self) -> None:
        """Client must be authenticated in order to access BAM version information."""
        try:
            sysinfo = self.getSystemInfo()
        except ErrorResponse as e:
            if "read only" in e.message:
                _LOGGER.warning(
                    'Unable to resolve system version for "%s". Cannot check if methods satisfy minimum version requirements.',
                    self._service.url,
                )
                return
            raise
        sysinfo = deserialize_joined_key_value_pairs(sysinfo)
        version = sysinfo["version"]  # e.g. '1.2.3-456.GA.bcn'
        version = version.split("-")[0]
        self._service.version = _Version(version)

    def __getattr__(self, item):
        """
        Wraps generic REST methods (attached to a ServiceBase instance) and
        passes to them the `requests` session.

        :param item: The method attribute being called.
        :return: The result of the call.
        """
        wrapped = getattr(self._service, item)

        def func_wrapper(*args, **kwargs):
            """
            Wrapper function that passes the `requests` session to use for the
            REST call.

            :param args: Positional arguments for the REST call.
            :param kwargs: Keyword arguments for the REST call.
            :return: Result of the REST call.
            """
            return wrapped(self.session, *args, **kwargs)

        return func_wrapper
