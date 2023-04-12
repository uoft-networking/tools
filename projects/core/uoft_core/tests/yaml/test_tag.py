# coding: utf-8

import pytest  # NOQA

from ._roundtrip import round_trip, round_trip_load, YAML

class TestIndentFailures:
    def test_tag(self):
        round_trip(
            """\
        !!python/object:__main__.Developer
        name: Anthon
        location: Germany
        language: python
        """
        )

    def test_full_tag(self):
        round_trip(
            """\
        !!tag:yaml.org,2002:python/object:__main__.Developer
        name: Anthon
        location: Germany
        language: python
        """
        )

    def test_standard_tag(self):
        round_trip(
            """\
        !!tag:yaml.org,2002:python/object:map
        name: Anthon
        location: Germany
        language: python
        """
        )

    def test_Y1(self):
        round_trip(
            """\
        !yyy
        name: Anthon
        location: Germany
        language: python
        """
        )

    def test_Y2(self):
        round_trip(
            """\
        !!yyy
        name: Anthon
        location: Germany
        language: python
        """
        )


class TestImplicitTaggedNodes:
    def test_scalar(self):
        round_trip(
            """\
        - !Scalar abcdefg
        """
        )

    def test_mapping(self):
        round_trip(
            """\
        - !Mapping {a: 1, b: 2}
        """
        )

    def test_sequence(self):
        yaml = YAML()
        yaml.brace_single_entry_mapping_in_flow_sequence = True
        yaml.mapping_value_align = True
        yaml.round_trip(
            """
        - !Sequence [a, {b: 1}, {c: {d: 3}}]
        """
        )

    def test_sequence2(self):
        yaml = YAML()
        yaml.mapping_value_align = True
        yaml.round_trip(
            """
        - !Sequence [a, b: 1, c: {d: 3}]
        """
        )
