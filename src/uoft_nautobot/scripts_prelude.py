"""
Through clever application of the `nautobot-server shell --command` option,
we can run arbitrary Python code with the full context of Nautobot's ORM and models.
This is a good way to run one-off scripts or quickly iterate on ideas before incorporating
them into nautobot commands or jobs

The purpose of this module is to gather up all the symbols made available to the nautobot shell
and provide a single import point for them so we can get proper typing support and auto-complete
in our scripts without having to tediously re-import every symbol we might need during prototyping
"""
# Shell Plus Model Imports
from constance.models import Constance
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    PeriodicTasks,
    SolarSchedule,
)
from django_celery_results.models import ChordCounter, GroupResult, TaskResult
from nautobot.circuits.models import Circuit, CircuitTermination, CircuitType, Provider, ProviderNetwork
from nautobot.cloud.models import (
    CloudAccount,
    CloudNetwork,
    CloudNetworkPrefixAssignment,
    CloudResourceType,
    CloudService,
    CloudServiceNetworkAssignment,
)
from nautobot.dcim.models.cables import Cable, CablePath
from nautobot.dcim.models.device_component_templates import (
    ConsolePortTemplate,
    ConsoleServerPortTemplate,
    DeviceBayTemplate,
    FrontPortTemplate,
    InterfaceTemplate,
    ModuleBayTemplate,
    PowerOutletTemplate,
    PowerPortTemplate,
    RearPortTemplate,
)
from nautobot.dcim.models.device_components import (
    ConsolePort,
    ConsoleServerPort,
    DeviceBay,
    FrontPort,
    Interface,
    InterfaceRedundancyGroup,
    InterfaceRedundancyGroupAssociation,
    InventoryItem,
    ModuleBay,
    PowerOutlet,
    PowerPort,
    RearPort,
)
from nautobot.dcim.models.devices import (
    Controller,
    ControllerManagedDeviceGroup,
    Device,
    DeviceFamily,
    DeviceRedundancyGroup,
    DeviceType,
    DeviceTypeToSoftwareImageFile,
    InterfaceVDCAssignment,
    Manufacturer,
    Module,
    ModuleType,
    Platform,
    SoftwareImageFile,
    SoftwareVersion,
    VirtualChassis,
    VirtualDeviceContext,
)
from nautobot.dcim.models.locations import Location, LocationType
from nautobot.dcim.models.power import PowerFeed, PowerPanel
from nautobot.dcim.models.racks import Rack, RackGroup, RackReservation
from nautobot.extras.models.change_logging import ObjectChange
from nautobot.extras.models.contacts import Contact, ContactAssociation, Team
from nautobot.extras.models.customfields import ComputedField, CustomField, CustomFieldChoice
from nautobot.extras.models.datasources import GitRepository
from nautobot.extras.models.groups import DynamicGroup, DynamicGroupMembership, StaticGroupAssociation
from nautobot.extras.models.jobs import (
    Job,
    JobButton,
    JobHook,
    JobLogEntry,
    JobQueue,
    JobQueueAssignment,
    JobResult,
    ScheduledJob,
    ScheduledJobs,
)
from nautobot.extras.models.metadata import MetadataChoice, MetadataType, ObjectMetadata
from nautobot.extras.models.models import (
    ConfigContext,
    ConfigContextSchema,
    CustomLink,
    ExportTemplate,
    ExternalIntegration,
    FileAttachment,
    FileProxy,
    GraphQLQuery,
    HealthCheckTestModel,
    ImageAttachment,
    Note,
    SavedView,
    UserSavedViewAssociation,
    Webhook,
)
from nautobot.extras.models.relationships import Relationship, RelationshipAssociation
from nautobot.extras.models.roles import Role
from nautobot.extras.models.secrets import Secret, SecretsGroup, SecretsGroupAssociation
from nautobot.extras.models.statuses import Status
from nautobot.extras.models.tags import Tag, TaggedItem
from nautobot.ipam.models import (
    IPAddress,
    IPAddressToInterface,
    Namespace,
    Prefix,
    PrefixLocationAssignment,
    RIR,
    RouteTarget,
    Service,
    VLAN,
    VLANGroup,
    VLANLocationAssignment,
    VRF,
    VRFDeviceAssignment,
    VRFPrefixAssignment,
)
from nautobot.tenancy.models import Tenant, TenantGroup
from nautobot.users.models import AdminGroup, ObjectPermission, User
from rest_framework.authtoken.models import Token, TokenProxy
from nautobot.virtualization.models import Cluster, ClusterGroup, ClusterType, VMInterface, VirtualMachine
from nautobot.wireless.models import (
    ControllerManagedDeviceGroupRadioProfileAssignment,
    ControllerManagedDeviceGroupWirelessNetworkAssignment,
    RadioProfile,
    SupportedDataRate,
    WirelessNetwork,
)
from nautobot_golden_config.models import (
    ComplianceFeature,
    ComplianceRule,
    ConfigCompliance,
    ConfigPlan,
    ConfigRemove,
    ConfigReplace,
    GoldenConfig,
    GoldenConfigSetting,
    RemediationSetting,
)
from nautobot_ssot.integrations.infoblox.models import SSOTInfobloxConfig
from nautobot_ssot.integrations.itential.models import AutomationGatewayModel
from nautobot_ssot.integrations.servicenow.models import SSOTServiceNowConfig
from nautobot_ssot.models import SSOTConfig, Sync, SyncLogEntry
from silk.models import Profile, Request, Response, SQLQuery
from social_django.models import Association, Code, Nonce, Partial, UserSocialAuth

# Shell Plus Django Imports
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Case, Count, F, Max, Min, Prefetch, Q, Sum, When
from django.utils import timezone
from django.urls import reverse
from django.db.models import Exists, OuterRef, Subquery

# [[[cog
# tasks._coghelpers.gen_prelude_exports()
# ]]]
__all__ = [
    "AdminGroup",
    "Association",
    "AutomationGatewayModel",
    "Avg",
    "Cable",
    "CablePath",
    "Case",
    "ChordCounter",
    "Circuit",
    "CircuitTermination",
    "CircuitType",
    "ClockedSchedule",
    "CloudAccount",
    "CloudNetwork",
    "CloudNetworkPrefixAssignment",
    "CloudResourceType",
    "CloudService",
    "CloudServiceNetworkAssignment",
    "Cluster",
    "ClusterGroup",
    "ClusterType",
    "Code",
    "ComplianceFeature",
    "ComplianceRule",
    "ComputedField",
    "ConfigCompliance",
    "ConfigContext",
    "ConfigContextSchema",
    "ConfigPlan",
    "ConfigRemove",
    "ConfigReplace",
    "ConsolePort",
    "ConsolePortTemplate",
    "ConsoleServerPort",
    "ConsoleServerPortTemplate",
    "Constance",
    "Contact",
    "ContactAssociation",
    "ContentType",
    "Controller",
    "ControllerManagedDeviceGroup",
    "ControllerManagedDeviceGroupRadioProfileAssignment",
    "ControllerManagedDeviceGroupWirelessNetworkAssignment",
    "Count",
    "CrontabSchedule",
    "CustomField",
    "CustomFieldChoice",
    "CustomLink",
    "Device",
    "DeviceBay",
    "DeviceBayTemplate",
    "DeviceFamily",
    "DeviceRedundancyGroup",
    "DeviceType",
    "DeviceTypeToSoftwareImageFile",
    "DynamicGroup",
    "DynamicGroupMembership",
    "Exists",
    "ExportTemplate",
    "ExternalIntegration",
    "F",
    "FileAttachment",
    "FileProxy",
    "FrontPort",
    "FrontPortTemplate",
    "GitRepository",
    "GoldenConfig",
    "GoldenConfigSetting",
    "GraphQLQuery",
    "Group",
    "GroupResult",
    "HealthCheckTestModel",
    "IPAddress",
    "IPAddressToInterface",
    "ImageAttachment",
    "Interface",
    "InterfaceRedundancyGroup",
    "InterfaceRedundancyGroupAssociation",
    "InterfaceTemplate",
    "InterfaceVDCAssignment",
    "IntervalSchedule",
    "InventoryItem",
    "Job",
    "JobButton",
    "JobHook",
    "JobLogEntry",
    "JobQueue",
    "JobQueueAssignment",
    "JobResult",
    "Location",
    "LocationType",
    "LogEntry",
    "Manufacturer",
    "Max",
    "MetadataChoice",
    "MetadataType",
    "Min",
    "Module",
    "ModuleBay",
    "ModuleBayTemplate",
    "ModuleType",
    "Namespace",
    "Nonce",
    "Note",
    "ObjectChange",
    "ObjectMetadata",
    "ObjectPermission",
    "OuterRef",
    "Partial",
    "PeriodicTask",
    "PeriodicTasks",
    "Permission",
    "Platform",
    "PowerFeed",
    "PowerOutlet",
    "PowerOutletTemplate",
    "PowerPanel",
    "PowerPort",
    "PowerPortTemplate",
    "Prefetch",
    "Prefix",
    "PrefixLocationAssignment",
    "Profile",
    "Provider",
    "ProviderNetwork",
    "Q",
    "RIR",
    "Rack",
    "RackGroup",
    "RackReservation",
    "RadioProfile",
    "RearPort",
    "RearPortTemplate",
    "Relationship",
    "RelationshipAssociation",
    "RemediationSetting",
    "Request",
    "Response",
    "Role",
    "RouteTarget",
    "SQLQuery",
    "SSOTConfig",
    "SSOTInfobloxConfig",
    "SSOTServiceNowConfig",
    "SavedView",
    "ScheduledJob",
    "ScheduledJobs",
    "Secret",
    "SecretsGroup",
    "SecretsGroupAssociation",
    "Service",
    "Session",
    "SoftwareImageFile",
    "SoftwareVersion",
    "SolarSchedule",
    "StaticGroupAssociation",
    "Status",
    "Subquery",
    "Sum",
    "SupportedDataRate",
    "Sync",
    "SyncLogEntry",
    "Tag",
    "TaggedItem",
    "TaskResult",
    "Team",
    "Tenant",
    "TenantGroup",
    "Token",
    "TokenProxy",
    "User",
    "UserSavedViewAssociation",
    "UserSocialAuth",
    "VLAN",
    "VLANGroup",
    "VLANLocationAssignment",
    "VMInterface",
    "VRF",
    "VRFDeviceAssignment",
    "VRFPrefixAssignment",
    "VirtualChassis",
    "VirtualDeviceContext",
    "VirtualMachine",
    "Webhook",
    "When",
    "WirelessNetwork",
    "cache",
    "get_user_model",
    "reverse",
    "settings",
    "timezone",
    "transaction",
]
# [[[end]]]
