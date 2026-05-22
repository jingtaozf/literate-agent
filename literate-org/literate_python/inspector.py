from inspect import getmembers, isbuiltin, ismethod
from typing import Dict
from datetime import datetime
from multimethod import multimethod


def stringify_val(member):
    key, val = member
    if isinstance(val, str):
        return key, '"{}"'.format(val)
    if type(val) in (dict, tuple, list):
        return key, _inspect(val)
    return key, f"{str(val)} {str(type(val))}"


def is_trash(member):
    key, val = member
    return (
        key in ["__doc__", "__class__", "__hash__", "__dict__"]
        or ismethod(val)
        or isbuiltin(val)
        or type(val).__name__ == "method-wrapper"
    )


def _pyinspect_inspect_object(obj):
    """
    Turns a **non-primitive** obj into a dictionary of its fields and their values.
    Filters out some built-in magic fields and pretty-prints dictionary values via `json.dumps`.
    Doesn't display methods.
    """
    return dict(stringify_val(m) for m in reversed(getmembers(obj)) if not is_trash(m))


def _pyinspect_add_quotes(key):
    """
    Surrounds string key with extra quotes because Emacs parses them as just symbols
    and makes it hard to distinguish between them and non-string symbols

    >>> _pyinspect_add_quotes("hello")
    '"hello"'

    >>> _pyinspect_add_quotes(1)
    1
    """
    return '"{}"'.format(key) if type(key) is str else key


def trim_seq(seq, elem_cap):
    if type(seq) is dict:
        return _pyinspect_take_dict(seq, elem_cap)
    elif type(seq) in (tuple, list):
        return seq[:elem_cap]


def _pyinspect_take_dict(d: Dict, n: int):
    "Returns a new dictionary with the first n pairs from d"

    def iterator():
        i = 0
        for item in d.items():
            if i == n:
                break
            yield item
            i += 1

    return dict(iterator())


@multimethod
def _inspect(obj) -> dict:
    return {"type": "object", "value": _pyinspect_inspect_object(obj)}


@_inspect.register  # type: ignore
def _(obj: str) -> dict:
    return {"type": "string", "value": obj}


@_inspect.register  # type: ignore
def _(obj: bool) -> dict:
    return {"type": "bool", "value": obj}


@_inspect.register  # type: ignore
def _(obj: int) -> dict:
    return {"type": "integer", "value": obj}


@_inspect.register  # type: ignore
def _(obj: float) -> dict:
    return {"type": "float", "value": obj}


@_inspect.register  # type: ignore
def _(obj: complex) -> dict:
    return {"type": "complex", "value": obj}


@_inspect.register  # type: ignore
def _(obj: tuple) -> dict:
    return {
        "type": "tuple",
        "value": [_inspect(item) for item in obj],
    }


@_inspect.register  # type: ignore
def _(obj: list) -> dict:
    return {
        "type": "list",
        "value": [_inspect(item) for item in obj],
    }


@_inspect.register  # type: ignore
def _(obj: dict) -> dict:
    return {
        "type": "dict",
        "value": {_pyinspect_add_quotes(k): _inspect(v) for (k, v) in obj.items()},
    }


@_inspect.register  # type: ignore
def _(obj: datetime) -> dict:
    print(f"obj: {obj}")
    return {
        "type": "datetime",
        "value": obj.isoformat(),
    }


# def _pyinspect_json(obj):
#     return json.dumps(_inspect(obj), indent=4, default=lambda o: _pyinspect(o)["value"])
