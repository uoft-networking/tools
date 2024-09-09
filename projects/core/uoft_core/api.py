"""
General abstractions for working with REST APIs
"""

from typing import Any, TYPE_CHECKING

from .typing import params_of
from requests import Session, Response, HTTPError
from typing_extensions import Self
from yarl import URL


class RESTAPIError(HTTPError):
    """An error raised when an API request fails.

    This error is raised when an API request fails, and the response is JSON.
    The error message is extracted from the JSON response.
    """

    data: dict[str, Any]

    def __init__(self, response: Response):
        try:
            error = response.json()
        except ValueError:
            # If the response is not JSON, just raise the original exception
            super().__init__(response=response)
        else:
            # If the response is JSON, raise a new exception with the JSON error message
            self.data = error
            super().__init__(response=response)

    def __repr__(self) -> str:
        return f"RESTAPIError({self.data})"

    def __str__(self) -> str:
        return (
            f"{self.response.status_code}: {self.response.reason} - "
            f"{self.data.get('message', self.data.get('error', self.data))}"
        )


class APIBase(Session):  # APIBase will be redeclared in a TYPE_CHECKING block below #type: ignore
    """A Requests session with a base URL.

    Provides cookie persistence, connection-pooling, and configuration.

    Args:
        base_url (str): The base URL of the REST API server.
        api_root (str, optional): The root path of the REST API, relative to the base URL. Defaults to '/'.

    Example:

        >>> import requests
        >>> s = requests.Session('https://<rest-api-server>/')
        >>> s.login()
        >>> s.get('/records')
        <Response [200]>
        >>> s.logout()

        Or as a context manager:

        >>> with requests.Session('https://<rest-api-server>/') as s:
        ...     s.get('/records')
        <Response [200]>
    """

    # At its core, an API wrapper is just a requests Session where all requests operate relative to a base URL,
    # and where some form of authentication needs to happen before requests can be made.
    def __init__(self, base_url: str, api_root: str = ""):
        super().__init__()
        # base_url may be a bare hostname, or a full URL (ie 'https://hostname')
        url = URL(base_url)
        if not url.scheme:
            url = url.with_scheme("https")
        self.url = url
        self.api_url = url / api_root
        self.hooks["response"].append(self.handle_errors)

    def handle_errors(self, response: Response, *args, **kwargs):
        try:
            response.raise_for_status()
        except HTTPError as e:
            raise RESTAPIError(response) from e
        return response

    def login(self):
        # login is called in __enter__, so it must not require any parameters.
        # All authentication data should be stored in the instance.
        # As a naive base example, we'll just assume that the login method is a no-op.
        pass

    def logout(self):
        # logout is called in __exit__, so it must not require any parameters.
        # As a naive base example, we'll just assume that the logout method is a no-op.
        pass

    def __enter__(self) -> Self:
        self.login()
        return super().__enter__()

    def __exit__(self, *args):
        self.logout()
        return super().__exit__(*args)

    def request(self, method: str, url: URL | str, **kwargs) -> Any:
        # If the URL is a string, join it with the api URL
        if isinstance(url, str):
            url = url.lstrip("/")
            url = self.api_url / url

        # convert URL to string before passing it on to the super class
        url = str(url)
        return super().request(method, url, **kwargs)


if TYPE_CHECKING:
    from requests.sessions import (
        _Auth,
        _TextMapping,
        _Params,
        _Verify,
        _Cert,
        RequestsCookieJar,
        _HeadersUpdateMapping,
        _Data,
        _Files,
        _Timeout,
        _HooksInput,
    )
    from _typeshed import Incomplete

    class APIBase(APIBase):
        def get(
            self,
            url: str | bytes | URL,
            *,
            params: _Params | None = ...,
            data: _Data | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
        def options(
            self,
            url: str | bytes | URL,
            *,
            params: _Params | None = ...,
            data: _Data | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
        def head(
            self,
            url: str | bytes | URL,
            *,
            params: _Params | None = ...,
            data: _Data | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
        def post(
            self,
            url: str | bytes | URL,
            data: _Data | None = None,
            json: Incomplete | None = None,
            *,
            params: _Params | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
        ) -> Response: ...
        def put(
            self,
            url: str | bytes | URL,
            data: _Data | None = None,
            *,
            params: _Params | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
        def patch(
            self,
            url: str | bytes | URL,
            data: _Data | None = None,
            *,
            params: _Params | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
        def delete(
            self,
            url: str | bytes | URL,
            *,
            params: _Params | None = ...,
            data: _Data | None = ...,
            headers: _HeadersUpdateMapping | None = ...,
            cookies: RequestsCookieJar | _TextMapping | None = ...,
            files: _Files | None = ...,
            auth: _Auth | None = ...,
            timeout: _Timeout | None = ...,
            allow_redirects: bool = ...,
            proxies: _TextMapping | None = ...,
            hooks: _HooksInput | None = ...,
            stream: bool | None = ...,
            verify: _Verify | None = ...,
            cert: _Cert | None = ...,
            json: Incomplete | None = ...,
        ) -> Response: ...
