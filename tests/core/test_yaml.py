from uoft_core import yaml, txt
from uoft_core.yaml import CommentedSeq


def test_yaml():
    t = yaml.to_yaml(
        {
            "hello": "world",
            "list": [1, 2, 3, 4],
        }
    )
    assert t == "hello: world\nlist:\n  - 1\n  - 2\n  - 3\n  - 4\n"
    s = yaml.from_yaml(
        txt(
            """
            hello: world # comment on scalar
            list: # comment on list
                - 1 # comment on list item

            # comment IN list
                - 2
                - 3 # another comment
                - 4
            set: !!set
                ? val # comment on set
                ? third
                ? other
            """
        )
    )
    assert isinstance(s, yaml.CommentedMap)
    assert isinstance(s["list"], CommentedSeq)
    c1 = yaml.get_comment(s["list"])
    assert c1 == "comment on list"
    c2 = yaml.get_comment(s["list"], 0)
    assert isinstance(c2, str)
    assert "comment on list item" in c2
    c3 = yaml.get_comment(s["list"], 1)  # type: ignore
    assert c3 is None
    print(yaml.to_yaml(s))
