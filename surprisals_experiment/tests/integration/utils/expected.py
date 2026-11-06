import json

from utils.world import REMOVED


def masked(expected, actual):
    """`actual` with every value `expected` marks `...` replaced by `...`."""
    if expected is ...:
        return ...
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: masked(expected[key], value) if key in expected else value for key, value in actual.items()}
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)) and len(expected) == len(actual):
        return type(actual)(masked(e, a) for e, a in zip(expected, actual))
    return actual


def decoded(expected, content):
    """File bytes in the form `expected` is written in."""
    if content is REMOVED:
        return content
    if isinstance(expected, str):
        return content.decode()
    if isinstance(expected, dict):
        return masked(expected, json.loads(content))
    if isinstance(expected, list):
        return masked(expected, [json.loads(line) for line in content.splitlines()])
    return masked(expected, content)


def described(outcome):
    return (type(outcome), str(outcome)) if isinstance(outcome, BaseException) else outcome
