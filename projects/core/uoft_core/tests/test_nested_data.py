# pylint: disable=unused-argument
from uoft_core import NestedData


def test_nesteddata_unstructure():
    input_data = {
        "menu": {
            "header": "SVG Viewer",
            "items": [
                {"id": "Open"},
                {"id": "OpenNew", "label": "Open New"},
                None,
                {"id": "ZoomIn", "label": "Zoom In"},
                {"id": "ZoomOut", "label": "Zoom Out"},
                {"id": "OriginalView", "label": "Original View"},
                None,
                {"id": "Quality"},
                {"id": "Pause"},
                {"id": "Mute"},
                None,
                {"id": "Find", "label": "Find..."},
                {"id": "FindAgain", "label": "Find Again"},
                {"id": "Copy"},
                {"id": "CopyAgain", "label": "Copy Again"},
                {"id": "CopySVG", "label": "Copy SVG"},
                {"id": "ViewSVG", "label": "View SVG"},
                {"id": "ViewSource", "label": "View Source"},
                {"id": "SaveAs", "label": "Save As"},
                None,
                {"id": "Help"},
                {"id": "About", "label": "About Adobe CVG Viewer..."},
            ],
            "other": {"[key1]": True, "[key2]": False},
        }
    }
    expected_output = [
        ("menu.header", "SVG Viewer"),
        ("menu.items.[0].id", "Open"),
        ("menu.items.[1].id", "OpenNew"),
        ("menu.items.[1].label", "Open New"),
        ("menu.items.[2]", None),
        ("menu.items.[3].id", "ZoomIn"),
        ("menu.items.[3].label", "Zoom In"),
        ("menu.items.[4].id", "ZoomOut"),
        ("menu.items.[4].label", "Zoom Out"),
        ("menu.items.[5].id", "OriginalView"),
        ("menu.items.[5].label", "Original View"),
        ("menu.items.[6]", None),
        ("menu.items.[7].id", "Quality"),
        ("menu.items.[8].id", "Pause"),
        ("menu.items.[9].id", "Mute"),
        ("menu.items.[10]", None),
        ("menu.items.[11].id", "Find"),
        ("menu.items.[11].label", "Find..."),
        ("menu.items.[12].id", "FindAgain"),
        ("menu.items.[12].label", "Find Again"),
        ("menu.items.[13].id", "Copy"),
        ("menu.items.[14].id", "CopyAgain"),
        ("menu.items.[14].label", "Copy Again"),
        ("menu.items.[15].id", "CopySVG"),
        ("menu.items.[15].label", "Copy SVG"),
        ("menu.items.[16].id", "ViewSVG"),
        ("menu.items.[16].label", "View SVG"),
        ("menu.items.[17].id", "ViewSource"),
        ("menu.items.[17].label", "View Source"),
        ("menu.items.[18].id", "SaveAs"),
        ("menu.items.[18].label", "Save As"),
        ("menu.items.[19]", None),
        ("menu.items.[20].id", "Help"),
        ("menu.items.[21].id", "About"),
        ("menu.items.[21].label", "About Adobe CVG Viewer..."),
        ("menu.other.[key1]", True),
        ("menu.other.[key2]", False),
    ]

    output = []
    for keypath, value in NestedData.unstructure(input_data):
        assert isinstance(keypath, str)
        output.append((keypath, value))
    assert output == expected_output


def test_nesteddata_restructure():
    input_data = [
        ("menu.header", "SVG Viewer"),
        ("menu.items.[0].id", "Open"),
        ("menu.items.[1].id", "OpenNew"),
        ("menu.items.[1].label", "Open New"),
        ("menu.items.[2]", None),
        ("menu.items.[3].id", "ZoomIn"),
        ("menu.items.[3].label", "Zoom In"),
        ("menu.items.[4].id", "ZoomOut"),
        ("menu.items.[4].label", "Zoom Out"),
        ("menu.items.[5].id", "OriginalView"),
        ("menu.items.[5].label", "Original View"),
        ("menu.items.[6]", None),
        ("menu.items.[7].id", "Quality"),
        ("menu.items.[8].id", "Pause"),
        ("menu.items.[9].id", "Mute"),
        ("menu.items.[10]", None),
        ("menu.items.[11].id", "Find"),
        ("menu.items.[11].label", "Find..."),
        ("menu.items.[12].id", "FindAgain"),
        ("menu.items.[12].label", "Find Again"),
        ("menu.items.[13].id", "Copy"),
        ("menu.items.[14].id", "CopyAgain"),
        ("menu.items.[14].label", "Copy Again"),
        ("menu.items.[15].id", "CopySVG"),
        ("menu.items.[15].label", "Copy SVG"),
        ("menu.items.[16].id", "ViewSVG"),
        ("menu.items.[16].label", "View SVG"),
        ("menu.items.[17].id", "ViewSource"),
        ("menu.items.[17].label", "View Source"),
        ("menu.items.[18].id", "SaveAs"),
        ("menu.items.[18].label", "Save As"),
        ("menu.items.[19]", None),
        ("menu.items.[20].id", "Help"),
        ("menu.items.[21].id", "About"),
        ("menu.items.[21].label", "About Adobe CVG Viewer..."),
        ("menu.other.[key1]", True),
        ("menu.other.[key2]", False),
    ]
    expected_output = {
        "menu": {
            "header": "SVG Viewer",
            "items": [
                {"id": "Open"},
                {"id": "OpenNew", "label": "Open New"},
                None,
                {"id": "ZoomIn", "label": "Zoom In"},
                {"id": "ZoomOut", "label": "Zoom Out"},
                {"id": "OriginalView", "label": "Original View"},
                None,
                {"id": "Quality"},
                {"id": "Pause"},
                {"id": "Mute"},
                None,
                {"id": "Find", "label": "Find..."},
                {"id": "FindAgain", "label": "Find Again"},
                {"id": "Copy"},
                {"id": "CopyAgain", "label": "Copy Again"},
                {"id": "CopySVG", "label": "Copy SVG"},
                {"id": "ViewSVG", "label": "View SVG"},
                {"id": "ViewSource", "label": "View Source"},
                {"id": "SaveAs", "label": "Save As"},
                None,
                {"id": "Help"},
                {"id": "About", "label": "About Adobe CVG Viewer..."},
            ],
            "other": {"[key1]": True, "[key2]": False},
        }
    }
    output = NestedData.restructure(input_data)
    assert output == expected_output


def test_nesteddata_remap():
    keymap = [
        # basic renaming
        ("menu.header", "menu.footer"),
        # renaming with shell-style wildcards
        ("menu.items.[1].*", "menu.items.[1].new*"),
        # multiple rules can be applied to the same items, will be applied in order
        ("menu.items.*", "menu.newitems.*"),
        # support multiple wildcards
        ("menu.*.[3].*", "menu.*.[3].*altered"),
        # can move entire branches of the tree around, reattach them to other parts of the tree
        ("menu.newitems.[4].*", "menu.newsubkey.*"),
    ]
    input_data = {
        "menu": {
            "header": "SVG Viewer",
            "items": [
                {"id": "Open"},
                {"id": "OpenNew", "label": "Open New"},
                None,
                {"id": "ZoomIn", "label": "Zoom In"},
                {"id": "ZoomOut", "label": "Zoom Out"},
            ],
            "other": {"[key1]": True, "[key2]": False},
        }
    }
    expected_output = {
        "menu": {
            "footer": "SVG Viewer",
            "newitems": [
                {"id": "Open"},
                {"newid": "OpenNew", "newlabel": "Open New"},
                None,
                {"idaltered": "ZoomIn", "labelaltered": "Zoom In"},
            ],
            "newsubkey": {"id": "ZoomOut", "label": "Zoom Out"},
            "other": {"[key1]": True, "[key2]": False},
        }
    }
    unstructured = NestedData.unstructure(input_data)
    unstructured = NestedData.remap(unstructured, keymap)
    output = NestedData.restructure(unstructured)
    assert output == expected_output


def test_nesteddata_filter():
    input_data = {
        "menu": {
            "header": "SVG Viewer",
            "items": [
                {"id": "Open"},
                {"id": "OpenNew", "label": "Open New"},
                None,
                {"id": "ZoomIn", "label": "Zoom In"},
                {"id": "ZoomOut", "label": "Zoom Out"},
                {"id": "OriginalView", "label": "Original View"},
                None,
                {"id": "Quality"},
                {"id": "Pause"},
                {"id": "Mute"},
                None,
                {"id": "Find", "label": "Find..."},
                {"id": "FindAgain", "label": "Find Again"},
                {"id": "Copy"},
                {"id": "CopyAgain", "label": "Copy Again"},
                {"id": "CopySVG", "label": "Copy SVG"},
                {"id": "ViewSVG", "label": "View SVG"},
                {"id": "ViewSource", "label": "View Source"},
                {"id": "SaveAs", "label": "Save As"},
                None,
                {"id": "Help"},
                {"id": "About", "label": "About Adobe CVG Viewer..."},
            ],
            "other": {
                "first": {"id": "Help"},
                "second": {"id": "Help"},
            },
        }
    }
    filters = [
        "menu.header",  # full match
        "menu.other.first",  # partial match
        "menu.items.*.*",  # regex match, filter out all entries in items which don't have an id
    ]
    expected_output = {
        "menu": {
            "header": "SVG Viewer",
            "items": [
                {"id": "Open"},
                {"id": "OpenNew", "label": "Open New"},
                {"id": "ZoomIn", "label": "Zoom In"},
                {"id": "ZoomOut", "label": "Zoom Out"},
                {"id": "OriginalView", "label": "Original View"},
                {"id": "Quality"},
                {"id": "Pause"},
                {"id": "Mute"},
                {"id": "Find", "label": "Find..."},
                {"id": "FindAgain", "label": "Find Again"},
                {"id": "Copy"},
                {"id": "CopyAgain", "label": "Copy Again"},
                {"id": "CopySVG", "label": "Copy SVG"},
                {"id": "ViewSVG", "label": "View SVG"},
                {"id": "ViewSource", "label": "View Source"},
                {"id": "SaveAs", "label": "Save As"},
                {"id": "Help"},
                {"id": "About", "label": "About Adobe CVG Viewer..."},
            ],
            "other": {"first": {"id": "Help"}},
        }
    }

    unstructured = NestedData.unstructure(input_data)
    filtered = NestedData.filter_(unstructured, filters)
    output = NestedData.restructure(filtered)
    assert output == expected_output
