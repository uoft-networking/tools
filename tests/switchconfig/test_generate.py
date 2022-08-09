# pylint: disable=unused-argument
from pathlib import Path
from typing import TYPE_CHECKING

from uoft_switchconfig.generate import render_template, model_questionnaire
from uoft_switchconfig.util import create_python_module
from uoft_core import txt

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from . import MockedConfig, MockPTApp

template_dir = Path(__file__).parent.joinpath("templates")


def test_model_questionnaire(mock_config: "MockedConfig", mock_pt_app: "MockPTApp"):
    mod = create_python_module(
        "test_model_questionnaire", template_dir.joinpath("data-model-test.py")
    )
    assert hasattr(mod, "Model")
    Model = getattr(mod, "Model")

    app = mock_pt_app
    app.input.send_text("deskswitch\n")  # usage
    app.input.send_text("test_userid\n")  # userid (from Deskswitch tagged union model)
    app.input.send_text("AC\n")  # building code
    app.input.send_text("207\n")  # room code
    app.input.send_text("10.0.1.0/24\n")  # network
    app.input.send_text("10.0.1.1\n")  # ip
    res = model_questionnaire(Model, {})
    assert res == Model(
        switch={
            "usage": {"kind": "deskswitch", "user_id": "test_userid"},
            "building_code": "AC",
            "room_code": "207",
            "network": "10.0.1.0/24",
            "ip": "10.0.1.1",
        }
    )


def test_render_from_question_block(mock_config: "MockedConfig"):
    answers = {
        "usage": "podium",
        "building_code": "AC",
        "room_code": "207",
        "tr_code": "2c",
        "user_id": "",
        "network": "10.0.1.0/24",
        "ip": "10.0.1.33",
    }
    res = render_template(
        template_dir.joinpath("comment-block-schema-test.j2"), input_data=answers
    )
    assert res == txt(
        """
        
        hostname av-ac207

        vtp domain AC

        #podium vlan config

        ip default-gateway 10.0.1.1

        site-id "av-ac207"

        #podium interface config

        switchport trunk allowed vlan 100,305,310,900

        ip address 10.0.1.33 255.255.255.0


        snmp-server location AC207
        """
    )


def test_render_from_model(mock_config: "MockedConfig"):
    answers = {
        "switch": {
            "usage": {"kind": "podium"},
            "building_code": "AC",
            "room_code": "207",
            "network": "10.0.1.0/24",
            "ip": "10.0.1.33",
        }
    }
    res = render_template(template_dir.joinpath("data-model-test.j2"), answers)
    assert res == txt(
        """
        hostname av-ac207

        vtp domain AC

        #podium vlan config

        ip default-gateway 10.0.1.1

        site-id "av-ac207"

        #podium interface config

        switchport trunk allowed vlan 100,305,310,900

        ip address 10.0.1.33 255.255.255.0


        snmp-server location AC207
        """
    )
