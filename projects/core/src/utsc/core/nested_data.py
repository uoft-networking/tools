import re
from typing import Any, Iterable

UnStructuredData = Iterable[tuple[str, Any]]
RegexOrString = str | re.Pattern[str]


class NestedData:
    """
    A collection of functions for working with nested data structures
    """

    @classmethod
    def unstructure(cls, data: Any) -> UnStructuredData:
        """
        Takes a data structure composed of arbitrarily nested dicts and lists,
        and breaks it down into a list of 2-tuples where the second element is a value,
        and the first element is a dotted string representing the datastructure path to that value.

        Args:
            data (Union[dict, list]):
                The nested data structure to unstructure.
                Can be a list or dict containing lists or dicts, to an almost infinite depth.

        Returns:
            List[Tuple[str, Any]]:
                a list of 2-tuples representing "leaf node" elements
                from the datastructure, and their keypaths.
        """
        if isinstance(data, list):
            for index, item in enumerate(data):
                keyname = f"[{index}]"
                for keypath, value in cls.unstructure(item):
                    keypath = f"{keyname}.{keypath}" if keypath else keyname
                    yield keypath, value
        elif isinstance(data, dict):
            for key, item in data.items():
                if not isinstance(key, str):
                    raise Exception(
                        "This function only supports dictionaries whose keys are strings"
                    )
                keyname = f'"{key}"' if " " in key else key
                for keypath, value in cls.unstructure(item):
                    keypath = f"{keyname}.{keypath}" if keypath else keyname
                    yield keypath, value
        else:
            # We've reached a leaf node in the data structure. return a falsy value as keypath so that previous
            # recursion uses its own keypath as the final keypath
            yield "", data

    @classmethod
    def restructure(cls, data: UnStructuredData) -> Any:
        """
        Takes a list of 2-tuples where the second element is a value,
        and the first element is a dotted string representing the datastructure path to that value,
        and reconstructs a nested datastructure from that information

        Args:
            data (List[Tuple[str, Any]]):
                a list of 2-tuples representing "leaf node" elements
                from the datastructure, and their keypaths.

        Returns:
            Union[dict, list]:
                The nested data structure, reconstructed.
                Can be a list or dict containing lists or dicts, to an almost infinite depth.
        """

        # The first thing we want to do is group items from the list based on the first element of their keypath.
        # All items sharing a common first element of a keypath belong to the same nested dict/list
        root_names: dict[str, Any] = {}
        for keypath, value in data:
            key, _, keypath = keypath.partition(".")

            if key not in root_names:
                root_names[key] = []
            root_names[key].append((keypath, value))

        # Now, to reconstruct the object. The keys in root_names can either be all strings
        # (meaning this object is a dict), or they can all strings of the pattern '[#]'
        # representing list indices, or they can be blank, meaning we've reached "leaf nodes" in the data tree.
        # in order to figure out which object to reconstruct,
        # we need to know what kind of keys we're dealing with
        if len(root_names) == 1 and list(root_names.keys())[0] == "":
            # We've reached a "leaf node"
            return root_names[""][0][1]

        def is_index_key(k: str) -> bool:
            return k.startswith("[") and k.endswith("]") and k[1:-1].isdecimal()

        if all(is_index_key(key) for key in root_names):
            # All keys match the pattern for index keys (numbers wrapped in square brackets)
            result = []
            for value in root_names.values():
                r = cls.restructure(value)
                result.append(r)
        else:
            # This is a dict
            result = {}
            for key, value in root_names.items():
                r = cls.restructure(value)
                result[key] = r
        return result

    @classmethod
    def _compile_keys_if_needed(
        cls, from_key: str, to_key: str = ""
    ) -> tuple[RegexOrString, str]:
        new_key1, new_key2 = from_key, to_key
        if "*" in new_key1:
            # This is a wildcard match and replace
            # in order to do a wildcard match, we need to convert the from_key string into a regex pattern,
            # and replace the escaped shell-style '*' wildcards with regex-style '.*' wildcards
            # we need to escape this string first so that legitimate characters in it (like '[' and ']') aren't
            # interpreted as regex symbols
            new_key1 = re.escape(new_key1).replace("\\*", "(.*)")
            new_key1 = re.compile(new_key1)
            # we also need to convert to_key into a regex replace string (replace the '*' wildcard symbols
            # with capture group backreferences '\#')
            # this part's a little bit trickier, since each such instance must be enumerated and assigned an index
            occurences = new_key2.count("*")
            for i in range(occurences):
                ref = i + 1
                new_key2 = new_key2.replace("*", f"\\{ref}", 1)
        return new_key1, new_key2

    @classmethod
    def remap(
        cls, data: UnStructuredData, key_map: list[tuple[str, str]]
    ) -> UnStructuredData:
        result = list(data)
        for from_key, to_key in key_map:
            from_key, to_key = cls._compile_keys_if_needed(from_key, to_key)
            for index, tup in enumerate(result):
                key, value = tup
                if isinstance(from_key, re.Pattern):  # noqa
                    # do a regex substitution
                    new_key = re.sub(from_key, to_key, key)
                else:
                    # do a regular substitution
                    new_key = key.replace(from_key, to_key)
                result[index] = new_key, value
        return result

    @classmethod
    def filter_(cls, data: UnStructuredData, key_list: list[str]) -> UnStructuredData:
        def test(pattern, tup):
            if isinstance(pattern, re.Pattern):  # noqa
                return bool(re.match(pattern, tup[0]))
            # else:
            return bool(pattern in tup[0])

        filters_list = [cls._compile_keys_if_needed(key)[0] for key in key_list]

        for tup in data:
            # yield tup if it matches any of the filters
            for pat in filters_list:
                if test(pat, tup):
                    yield tup
                    break
