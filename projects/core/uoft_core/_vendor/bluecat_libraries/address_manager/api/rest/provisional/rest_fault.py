# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
REST API Specific exceptions.
"""
from suds import WebFault
from .....http_client import ErrorResponse


class Fault:
    """
    Wrapper for fault messages.
    """

    def __init__(self, fault):
        self.faultstring = "Server raised fault: %s" % fault


class RESTFault(WebFault, ErrorResponse):
    """
    Exception wrapper for REST that mimics suds' WebFault exception.
    """

    def __init__(self, fault, document=None):
        # Expected types:
        # * fault is str
        # * document is requests.Response
        # NOTE: Upcoming rename of parameters (will happen when use of RESTFault is replaced by
        # direct use of ErrorResponse):
        # * fault -> message
        # * document -> response
        f = Fault(fault)
        WebFault.__init__(self, f, document)
        ErrorResponse.__init__(self, f.faultstring, document)

    def __str__(self):
        return str(self.message)
