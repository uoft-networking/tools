# coding: utf-8

"""
various test cases for YAML files
"""

import sys
import io
import pytest  # NOQA
import platform

from ._roundtrip import round_trip, dedent, round_trip_load, round_trip_dump  # NOQA


class TestYAML:
    def test_backslash(self):
        round_trip(
            """
        handlers:
          static_files: applications/\\1/static/\\2
        """
        )

    def test_omap_out(self):
        # ordereddict mapped to !!omap
        from collections import OrderedDict

        x = OrderedDict([("a", 1), ("b", 2)])
        res = round_trip_dump(x, default_flow_style=False)
        assert res == dedent(
            """
        !!omap
        - a: 1
        - b: 2
        """
        )

    def test_omap_roundtrip(self):
        round_trip(
            """
        !!omap
        - a: 1
        - b: 2
        - c: 3
        - d: 4
        """
        )

    @pytest.mark.skipif(sys.version_info < (2, 7), reason="collections not available")
    def test_dump_collections_ordereddict(self):
        from collections import OrderedDict
        import uoft_core.yaml  # NOQA

        # OrderedDict mapped to !!omap
        x = OrderedDict([("a", 1), ("b", 2)])
        res = round_trip_dump(x, default_flow_style=False)
        assert res == dedent(
            """
        !!omap
        - a: 1
        - b: 2
        """
        )

    @pytest.mark.skipif(
        sys.version_info >= (3, 0) or platform.python_implementation() != "CPython",
        reason="uoft_core.yaml not available",
    )
    def test_dump_ruamel_ordereddict(self):
        from uoft_core.ordereddict import ordereddict
        import uoft_core.yaml  # NOQA

        # OrderedDict mapped to !!omap
        x = ordereddict([("a", 1), ("b", 2)])
        res = round_trip_dump(x, default_flow_style=False)
        assert res == dedent(
            """
        !!omap
        - a: 1
        - b: 2
        """
        )

    def test_CommentedSet(self):
        from uoft_core.yaml.constructor import CommentedSet

        s = CommentedSet(["a", "b", "c"])
        s.remove("b")
        s.add("d")
        assert s == CommentedSet(["a", "c", "d"])
        s.add("e")
        s.add("f")
        s.remove("e")
        assert s == CommentedSet(["a", "c", "d", "f"])

    # ordering is not preserved in a set
    def test_set_compact(self):
        # this format is read and also should be written by default
        round_trip(
            """
        !!set
        ? a
        ? b
        ? c
        """
        )

    def test_blank_line_after_comment(self):
        round_trip(
            """
        # Comment with spaces after it.


        a: 1
        """
        )

    def test_blank_line_between_seq_items(self):
        round_trip(
            """
        # Seq with empty lines in between items.
        b:
        - bar


        - baz
        """
        )

    @pytest.mark.skipif(
        platform.python_implementation() == "Jython",
        reason="Jython throws RepresenterError",
    )
    def test_blank_line_after_literal_chip(self):
        s = """
        c:
        - |
          This item
          has a blank line
          following it.

        - |
          To visually separate it from this item.

          This item contains a blank line.


        """
        d = round_trip_load(dedent(s))
        print(d)
        round_trip(s)
        assert d["c"][0].split("it.")[1] == "\n"
        assert d["c"][1].split("line.")[1] == "\n"

    @pytest.mark.skipif(
        platform.python_implementation() == "Jython",
        reason="Jython throws RepresenterError",
    )
    def test_blank_line_after_literal_keep(self):
        """have to insert an eof marker in YAML to test this"""
        s = """
        c:
        - |+
          This item
          has a blank line
          following it.

        - |+
          To visually separate it from this item.

          This item contains a blank line.


        ...
        """
        d = round_trip_load(dedent(s))
        print(d)
        round_trip(s)
        assert d["c"][0].split("it.")[1] == "\n\n"
        assert d["c"][1].split("line.")[1] == "\n\n\n"

    @pytest.mark.skipif(
        platform.python_implementation() == "Jython",
        reason="Jython throws RepresenterError",
    )
    def test_blank_line_after_literal_strip(self):
        s = """
        c:
        - |-
          This item
          has a blank line
          following it.

        - |-
          To visually separate it from this item.

          This item contains a blank line.


        """
        d = round_trip_load(dedent(s))
        print(d)
        round_trip(s)
        assert d["c"][0].split("it.")[1] == ""
        assert d["c"][1].split("line.")[1] == ""

    def test_load_all_perserve_quotes(self):
        import uoft_core.yaml  # NOQA

        yaml = uoft_core.yaml.YAML()
        yaml.preserve_quotes = True
        s = dedent(
            """\
        a: 'hello'
        ---
        b: "goodbye"
        """
        )
        data = []
        for x in yaml.load_all(s):
            data.append(x)
        buf = uoft_core.yaml.compat.StringIO()
        yaml.dump_all(data, buf)
        out = buf.getvalue()
        print(type(data[0]["a"]), data[0]["a"])
        # out = uoft_core.yaml.round_trip_dump_all(data)
        print(out)
        assert out == s
