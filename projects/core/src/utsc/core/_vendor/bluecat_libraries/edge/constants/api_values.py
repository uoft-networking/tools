# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# pylint: disable=C0114,C0115,C0116;
"""Values related to the HTTP requests to and responses from BlueCat DNS Edge."""

import enum


class ErrorResponseCode(enum.Enum):
    """Values found as `code` in an error response from BlueCat DNS Edge."""

    # fmt: off
    BAD_REQUEST = 'BAD_REQUEST'                                # Request is invalid
    CLIENT_CREDENTIALS_INVALID = 'CLIENT_CREDENTIALS_INVALID'  # Client credentials are invalid
    ERROR_INVALID_ARGUMENT = 'ERROR_INVALID_ARGUMENT'          # Invalid request.
    INVALID_TOKENS_REQUEST = 'INVALID_TOKENS_REQUEST'          # Invalid token request body
    UNAUTHORIZED_ACTION = 'UNAUTHORIZED_ACTION'                # You are not authorized to perform this action
    USER_ALREADY_EXISTS = 'USER_ALREADY_EXISTS'                # User already exists.
    SITE_DOES_NOT_EXIST = 'SITE_DOES_NOT_EXIST'                # Site does not exist
