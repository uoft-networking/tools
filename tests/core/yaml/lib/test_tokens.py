import uoft_core.yaml
import pprint

# Tokens mnemonic:
# directive:            %
# document_start:       ---
# document_end:         ...
# alias:                *
# anchor:               &
# tag:                  !
# scalar                _
# block_sequence_start: [[
# block_mapping_start:  {{
# block_end:            ]}
# flow_sequence_start:  [
# flow_sequence_end:    ]
# flow_mapping_start:   {
# flow_mapping_end:     }
# entry:                ,
# key:                  ?
# value:                :

_replaces = {
    uoft_core.yaml.DirectiveToken: "%",
    uoft_core.yaml.DocumentStartToken: "---",
    uoft_core.yaml.DocumentEndToken: "...",
    uoft_core.yaml.AliasToken: "*",
    uoft_core.yaml.AnchorToken: "&",
    uoft_core.yaml.TagToken: "!",
    uoft_core.yaml.ScalarToken: "_",
    uoft_core.yaml.BlockSequenceStartToken: "[[",
    uoft_core.yaml.BlockMappingStartToken: "{{",
    uoft_core.yaml.BlockEndToken: "]}",
    uoft_core.yaml.FlowSequenceStartToken: "[",
    uoft_core.yaml.FlowSequenceEndToken: "]",
    uoft_core.yaml.FlowMappingStartToken: "{",
    uoft_core.yaml.FlowMappingEndToken: "}",
    uoft_core.yaml.BlockEntryToken: ",",
    uoft_core.yaml.FlowEntryToken: ",",
    uoft_core.yaml.KeyToken: "?",
    uoft_core.yaml.ValueToken: ":",
}


def test_tokens(data_filename, tokens_filename, verbose=False):
    tokens1 = []
    with open(tokens_filename, "r") as fp:
        tokens2 = fp.read().split()
    try:
        yaml = uoft_core.yaml.YAML(typ="unsafe", pure=True)
        with open(data_filename, "rb") as fp1:
            for token in yaml.scan(fp1):
                if not isinstance(
                    token,
                    (uoft_core.yaml.StreamStartToken, uoft_core.yaml.StreamEndToken),
                ):
                    tokens1.append(_replaces[token.__class__])
    finally:
        if verbose:
            print("TOKENS1:", " ".join(tokens1))
            print("TOKENS2:", " ".join(tokens2))
    assert len(tokens1) == len(tokens2), (tokens1, tokens2)
    for token1, token2 in zip(tokens1, tokens2):
        assert token1 == token2, (token1, token2)


test_tokens.unittest = [".data", ".tokens"]


def test_scanner(data_filename, canonical_filename, verbose=False):
    for filename in [data_filename, canonical_filename]:
        tokens = []
        try:
            yaml = uoft_core.yaml.YAML(typ="unsafe", pure=False)
            with open(filename, "rb") as fp:
                for token in yaml.scan(fp):
                    tokens.append(token.__class__.__name__)
        finally:
            if verbose:
                pprint.pprint(tokens)


test_scanner.unittest = [".data", ".canonical"]

if __name__ == "__main__":
    import test_appliance

    test_appliance.run(globals())
