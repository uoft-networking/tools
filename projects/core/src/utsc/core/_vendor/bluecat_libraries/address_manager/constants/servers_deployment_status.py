# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in GET /v1/getServerDeploymentStatus method in BlueCat Address Manager."""
from enum import IntEnum

from ._enum import StrEnum


class ServersDeploymentStatus(IntEnum):
    """Values of status codes for deployment of a particular server in BlueCat Address Manager."""

    EXECUTING = -1
    INITIALIZING = 0
    QUEUED = 1
    CANCELLED = 2
    FAILED = 3
    NOT_DEPLOYED = 4
    WARNING = 5
    INVALID = 6
    DONE = 7
    NO_RECENT_DEPLOYMENT = 8


class DeploymentTaskStatus(StrEnum):
    """
    Values of the overall deployment status and the deployment status of individual entities for deployment of
    a particular server in BlueCat Address Manager.
    """

    QUEUED = "QUEUED"
    STARTED = "STARTED"
    FINISHED = "FINISHED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
