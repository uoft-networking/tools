# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module with exceptions that may occur while working with BlueCat DNS Edge."""
from requests import Response
from ...http_client.exceptions import ErrorResponse

__all__ = ["EdgeErrorResponse"]


class EdgeErrorResponse(ErrorResponse):
    """
    Exception that represents the error HTTP response that was received, but
    additionally exposes the error code, reported by the Edge CI API.

    :param message: Text about the error that occurred.
    :type message: str
    :param response: The HTTP response resulting from a request.
    :type response: requests.Response
    :param code: A code identifying the problem.
    :type code: str
    """

    def __init__(self, message: str, response: Response, code: str, *args, **kwargs):
        super().__init__(message, response, *args, **kwargs)
        self.code = code
