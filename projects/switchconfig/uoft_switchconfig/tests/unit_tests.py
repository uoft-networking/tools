# flake8: noqa

from typing import TYPE_CHECKING
from pathlib import Path
from uoft_switchconfig import Settings
from uoft_switchconfig.cli import template_name_completion, console_name_completion
from uoft_switchconfig.generate import render_template, model_questionnaire
from uoft_core import txt
import pytest

from uoft_switchconfig.util import (
    CommentBlockField,
    get_comment_block_schema,
    model_source_from_comment_block_schema,
    construct_model_from_comment_block_schema,
)
from uoft_core import txt

if TYPE_CHECKING:
    from pytest_mock import MockFixture


SIMPLE_INTERMEDIARY = {
    "usage": CommentBlockField(
        name="usage",
        type="Literal['deskswitch', 'podium', 'access']",
        desc="One of: (deskswitch/podium/access), Example: deskswitch",
        default=None,
    ),
    "building_code": CommentBlockField(
        name="building_code",
        type="str",
        desc="(aka alpha code) Example: SW",
        default=None,
    ),
    "room_code": CommentBlockField(
        name="room_code", type="str", desc="Example: 254A", default=None
    ),
    "tr_code": CommentBlockField(
        name="tr_code", type="str", desc="Telecom Room code, Example: 2r", default=None
    ),
    "user_id": CommentBlockField(
        name="user_id",
        type="str",
        desc="UTSCID of the person this switch is for, Example: someuser",
        default=None,
    ),
    "network": CommentBlockField(
        name="network",
        type="ipaddress.IPv4Network",
        desc="network address in CIDR notation, Example: 10.14.1.0/24",
        default=None,
    ),
    "ip": CommentBlockField(
        name="ip",
        type="ipaddress.IPv4Address",
        desc="IP address of this switch, Example: 10.14.1.33",
        default=None,
    ),
}

ADVANCED_INTERMEDIARY = {
    "switch": {
        "usage": CommentBlockField(
            name="switch.usage",
            type="Literal['deskswitch', 'podium', 'access']",
            desc="One of: (deskswitch/podium/access), Example: deskswitch",
            default=None,
        ),
        "building_code": CommentBlockField(
            name="switch.building_code",
            type="str",
            desc="(aka alpha code) Example: SW",
            default=None,
        ),
        "room_code": CommentBlockField(
            name="switch.room_code", type="str", desc="Example: 254A", default="200E"
        ),
        "tr_code": CommentBlockField(
            name="switch.tr_code",
            type="str",
            desc="Telecom Room code, Example: 2r",
            default=None,
        ),
        "vlan_id": CommentBlockField(
            name="switch.vlan_id", type="int", desc="vlan number", default="500"
        ),
        "ip": {
            "address": CommentBlockField(
                name="switch.ip.address",
                type="ipaddress.IPv4Address",
                desc="IP address of this switch on the mgmt network, Example:",
                default=None,
            ),
            "network": CommentBlockField(
                name="switch.ip.network",
                type="ipaddress.IPv4Network",
                desc="network address  in CIDR notation, Example:",
                default=None,
            ),
        },
    }
}


class CLITests:
    "integration tests for the CLI code"
    def template_name_completion_test(self):
        class MockContext:
            params = {"cache_dir": Path(__file__).parent / "fixtures/templates"}

        res = template_name_completion(MockContext(), "")  # pyright: ignore[reportArgumentType]
        assert set(res) == set(
            [
                "comment-block-schema-test.j2",
                "data-model-test.j2",
                "subdirectory/template.j2",
                "subdirectory/other_template.j2",
            ]
        )

        res = template_name_completion(MockContext(), "subdir")  # pyright: ignore[reportArgumentType]
        assert set(res) == set(
            [
                "subdirectory/template.j2",
                "subdirectory/other_template.j2",
            ]
        )

        res = template_name_completion(MockContext(), "subdirectory/tem")  # pyright: ignore[reportArgumentType]
        assert set(res) == set(
            [
                "subdirectory/template.j2",
            ]
        )

    def console_name_completion_test(self, mocker: "MockFixture"):
        mock_settings = Settings(
            generate={"templates_dir": Path(__file__).parent / "templates"}, # type: ignore
            deploy=dict( # type: ignore
                ssh_pass_cmd="echo ssh_pass",
                terminal_pass_cmd="echo terminal_pass",
                enable_pass_cmd="echo enable_pass",
                targets=dict(
                    airconsole1="airconsole:4001",
                    airconsole2="airconsole:4002",
                    airconsole3="airconsole:4003",
                    airconsole4="airconsole:4004",
                    airconsole5="airconsole:4005",
                    airconsole6="airconsole:4006",
                    airconsole7="airconsole:4007",
                    airconsole8="airconsole:4008",
                    newconsole="console:22",
                )
            ),
        )
        mocker.patch.object(Settings, '_instance', mock_settings)
        res = console_name_completion("")
        assert set(res) == set(
            [
                "airconsole1",
                "airconsole2",
                "airconsole3",
                "airconsole4",
                "airconsole5",
                "airconsole6",
                "airconsole7",
                "airconsole8",
                "newconsole",
            ]
        )

        res = console_name_completion("newco")
        assert res == ["newconsole"]


class UtilTests:
    "Unit tests for uoft_switchconfig.util"

    def get_comment_block_schema_test(self):
        """
        Test get_comment_block_schema()
        """
        res = get_comment_block_schema(
            txt(
                """
            """
            )
        )
        assert res is None

        res = get_comment_block_schema(
            txt(
                """
            {#
            # variable_name | description | default_value
            #}
        """
            )
        )
        assert res is None

        res = get_comment_block_schema(
            txt(
                """
            {#
            # variable_name | type                                      | description?                                               | default_value
            usage           | Literal['deskswitch', 'podium', 'access'] | One of: (deskswitch/podium/access), Example: deskswitch    | 
            building_code   |                                           | (aka alpha code) Example: SW                               | 
            room_code       |                                           | Example: 254A                                              | 
            tr_code         |                                           | Telecom Room code, Example: 2r                             | 
            user_id         |                                           | UTSCID of the person this switch is for, Example: someuser | 
            network         | ipaddress.IPv4Network                               | network address in CIDR notation, Example: 10.14.1.0/24    | 
            ip              | ipaddress.IPv4Address                               | IP address of this switch, Example: 10.14.1.33             |
            #}
            some other text unrelated to the comment block
        """
            )
        )
        assert res == SIMPLE_INTERMEDIARY

        res = get_comment_block_schema(
            txt(
                """
                {#
                # variable_name | type                                      | description?                                              | default_value
                switch.usage           | Literal['deskswitch', 'podium', 'access'] | One of: (deskswitch/podium/access), Example: deskswitch   | 
                switch.building_code   |                                           | (aka alpha code) Example: SW                              | 
                switch.room_code       |                                           | Example: 254A                                             | 200E
                switch.tr_code         |                                           | Telecom Room code, Example: 2r                            | 
                switch.vlan_id         | int                                       | vlan number                                               | 500
                switch.ip.address      | ipaddress.IPv4Address                               | IP address of this switch on the mgmt network, Example:   |   
                switch.ip.network      | ipaddress.IPv4Network                               | network address  in CIDR notation, Example:               |
                #}
                some other text unrelated to the comment block
                """
            )
        )
        assert res == ADVANCED_INTERMEDIARY


    def model_source_from_comment_block_schema_test(self):
        schema = SIMPLE_INTERMEDIARY

        res = model_source_from_comment_block_schema(schema)

        assert res == txt(
            """
            from typing import *
            from pydantic.v1.types import *
            from ipaddress import *
            from netaddr import *
            from pydantic.v1 import BaseModel, Field
            from ipaddress import IPv4Network
            from ipaddress import IPv4Address


            class Model(BaseModel):
                usage: Literal['deskswitch', 'podium', 'access'] = Field(description="One of: (deskswitch/podium/access), Example: deskswitch")
                building_code: str = Field(description="(aka alpha code) Example: SW")
                room_code: str = Field(description="Example: 254A")
                tr_code: str = Field(description="Telecom Room code, Example: 2r")
                user_id: str = Field(description="UTSCID of the person this switch is for, Example: someuser")
                network: IPv4Network = Field(description="network address in CIDR notation, Example: 10.14.1.0/24")
                ip: IPv4Address = Field(description="IP address of this switch, Example: 10.14.1.33")
            
            """
        )

        schema = ADVANCED_INTERMEDIARY

        res = model_source_from_comment_block_schema(schema)

        assert res == txt(
            """
            from typing import *
            from pydantic.v1.types import *
            from ipaddress import *
            from netaddr import *
            from pydantic.v1 import BaseModel, Field
            from ipaddress import IPv4Address
            from ipaddress import IPv4Network


            class Ip(BaseModel):
                address: IPv4Address = Field(description="IP address of this switch on the mgmt network, Example:")
                network: IPv4Network = Field(description="network address  in CIDR notation, Example:")

            class Switch(BaseModel):
                usage: Literal['deskswitch', 'podium', 'access'] = Field(description="One of: (deskswitch/podium/access), Example: deskswitch")
                building_code: str = Field(description="(aka alpha code) Example: SW")
                room_code: str = Field(str("200E"), description="Example: 254A")
                tr_code: str = Field(description="Telecom Room code, Example: 2r")
                vlan_id: int = Field(int("500"), description="vlan number")
                ip: Ip 

            class Model(BaseModel):
                switch: Switch 

            """
        )


    def construct_model_from_comment_block_schema_test(self):
        from pydantic.v1 import BaseModel

        schema = SIMPLE_INTERMEDIARY

        res = construct_model_from_comment_block_schema(schema)

        assert issubclass(res, BaseModel)
        assert set(res.__fields__.keys()) == {
            "room_code",
            "usage",
            "building_code",
            "ip",
            "network",
            "user_id",
            "tr_code",
        }

        from pydantic.v1 import BaseModel

        schema = ADVANCED_INTERMEDIARY

        res = construct_model_from_comment_block_schema(schema)

        assert issubclass(res, BaseModel)
        assert set(res.__fields__.keys()) == {
            "switch",
        }
        subtype = res.__fields__["switch"].type_
        assert subtype.__name__ == "Switch"
        assert issubclass(subtype, BaseModel)
        assert set(subtype.__fields__.keys()) == {
            "usage",
            "ip",
            "vlan_id",
            "tr_code",
            "room_code",
            "building_code",
        }
