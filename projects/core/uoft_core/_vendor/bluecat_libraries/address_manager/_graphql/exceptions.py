# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module with exceptions that may occur while working with BlueCat Address Manager's GraphQL API"""
from typing import Any, Optional

from requests import Response

from ...http_client.exceptions import ErrorResponse


class GraphQLException(ErrorResponse):
    """
    Exception that represents the the errors received from the GraphQL API.

    If this is an HTTP 400+ error, the ``errors`` attribute will be ``None``. If this is a GraphQL
    error, the ``errors`` attribute will be the ``errors`` field of the GraphQL response body.

    The ``message`` attribute is meant to be readable for humans. Do not parse it programmatically;
    use the ``response`` and ``errors`` attributes instead.
    """

    def __init__(
        self,
        message: str,
        response: Response,
        errors: Optional[list[dict[str, Any]]],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(message, response, *args, **kwargs)
        self.errors = errors
