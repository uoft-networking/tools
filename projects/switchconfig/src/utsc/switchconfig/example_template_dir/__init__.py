"""
All template directories for switchconfig must contain an __init__.py file which exposes the following:

PATH: a Path object pointing to the template folder itself
Filters: a class full of static methods to be included as filter functions in the jinja template engine
GLOBALS: a dictionary of variables to be included in the jinja template engine
process_template_data: a function which takes a template name, and an optional dictionary of variables, 
    and returns a dictionary of variables to feed into the template

The process_template_data function in this template module demonstrates two different ways of 
interactively getting and validating template data
"""

from ipaddress import IPv4Network, IPv4Address
from pathlib import Path
from typing import Any, Literal, Union

from utsc.switchconfig.generate import (
    model_questionnaire,
    validate_data_from_comment_block_schema,
    Choice,
)
from pydantic import BaseModel, Field

PATH = Path(__file__).parent


class Filters:
    """
    Container class for a bunch of filter functions.
    Every function defined in this class is made available as a jinja filter
    """

    @staticmethod
    def gateway_ip(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the IP address of the default gateway.
        Example: {{subnet|gateway_ip}} where example subnet 10.0.0.0/24 produces 10.0.0.1
        """
        return str(next(IPv4Network(subnet).hosts()))

    @staticmethod
    def network_address(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the network address of that network
        """
        return str(IPv4Network(subnet).network_address)

    @staticmethod
    def network_mask(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the network address of that network
        """
        return str(IPv4Network(subnet).netmask)

    @staticmethod
    def remap(key: str, map_name: str) -> str:
        """look up a key in a specific map/dict, and return its value"""
        m = {
            "usages": {
                "podium": "av",
                "deskswitch": "a1",
                "access": "a1",
            }
        }
        d = m[map_name]
        return d[key]


GLOBALS = {}


class DeskSwitch(Choice):
    kind: Literal["deskswitch"]
    user_id: str = Field(
        description="user_id of the person this deskswitch is for, Example: someuser"
    )


class Podium(Choice):
    kind: Literal["podium"]


class Access(Choice):
    kind: Literal["access"]
    tr_code: str = Field(description="Telecom Room code, Example: 2r")


class ExampleModel(BaseModel):
    usage: Union[DeskSwitch, Podium, Access]
    building_code: str = Field(description="(aka alpha code) Example: SW")
    room_code: str = Field(description="Example: 254A")
    network: IPv4Network = Field(
        description="network address of the mgmt network in CIDR notation, Example: 10.14.1.0/24"
    )
    ip: IPv4Address = Field(
        description="IP address of this switch on the mgmt network, Example: 10.14.1.33"
    )

    @property
    def hostname(self):
        prefix = Filters.remap(self.usage.kind, "usages")
        res = f"{prefix}-"
        if isinstance(self.usage, DeskSwitch):
            res += self.usage.user_id
        elif isinstance(self.usage, Podium):
            res += self.building_code + self.room_code
        elif isinstance(self.usage, Access):
            res += self.building_code + self.usage.tr_code
        return res.lower()

    @property
    def is_podium(self):
        return isinstance(self.usage, Podium)

    @property
    def is_deskswitch(self):
        return isinstance(self.usage, DeskSwitch)

    @property
    def is_access(self):
        return isinstance(self.usage, Access)


def process_template_data(
    template_name: str, input_data: dict[str, Any]
) -> dict[str, Any]:
    template_file = PATH / template_name
    if template_name == "comment-block-schema-example.j2":
        return validate_data_from_comment_block_schema(template_file, input_data)
    if template_name == "data-model-example.j2":
        input_data = model_questionnaire(ExampleModel, input_data=input_data)
        return dict(
            d=ExampleModel(**input_data),
        )
    # else:
    return input_data
