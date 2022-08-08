# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# pylint: disable=C0112,C0115,C0116,W0511;
"""Module with exceptions that may occur while working with BlueCat Address Manager and Edge APIs."""


class GeneralError(Exception):
    """
    Base exception to serve as an ancestor for the specific ones.

    :param message: Text about the error that occurred.
    :type message: str
    """

    def __init__(self, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ClientError(GeneralError):
    """
    Exception that is raised then a client encounters a problem not resulting from
    performing a request or processing its response.

    :param message: Text about the error that occurred.
    :type message: str
    """


class ErrorResponse(GeneralError):
    """
    This exception is raised when an error response is received from a target
    service, e.g., Edge CI API. The HTTP response is available via the `response`
    instance member.

    :param message: Text about the error that occurred.
    :type message: str
    :param response: The HTTP response resulting from a request.
    :type response: requests.Response
    """

    def __init__(self, message, response, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.response = response


class UnexpectedResponse(ErrorResponse):
    """
    This is a specific case of an exception about a response. It is used in the
    cases where the response itself was not an error, but it is not as expected
    based on documentation or contract.

    :param message: Text about the error that occurred.
    :type message: str
    :param response: The HTTP response resulting from a request.
    :type response: requests.Response
    """
