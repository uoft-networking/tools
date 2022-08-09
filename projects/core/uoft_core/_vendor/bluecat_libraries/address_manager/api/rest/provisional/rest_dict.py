# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Wrappers for standard dictionary REST results to make them mimic `suds`
dictionary results.
"""
from copy import deepcopy


class RESTDict(dict):
    """
    Wrapper for standard dictionary REST results to make them mimic `suds`
    dictionary results.
    """

    def __getattr__(self, item):
        return self[item]

    def __getstate__(self):
        pass

    def __setattr__(self, key, value):
        self[key] = value

    def __deepcopy__(self, memo):
        cls = self.__class__
        res = deepcopy(super(RESTDict, self))  # pylint: disable=super-with-arguments; legacy code
        return cls(res)
