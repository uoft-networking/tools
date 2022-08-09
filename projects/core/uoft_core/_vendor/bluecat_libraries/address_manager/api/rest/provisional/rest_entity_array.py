# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Wrapper for standard list REST results to make them mimic `suds` list results.
"""

from .rest_dict import RESTDict


class RESTEntityArray(list):
    """
    Wrapper for standard list REST results to make them mimic `suds` list results.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for index, entity in enumerate(self):
            if isinstance(entity, dict):
                self[index] = RESTDict(entity)

    @property
    def item(self):
        """
        Property provided for compatibility with `suds` list result.
        Points at the instance itself.
        """
        return self
