class StreamException(Exception):
    """Base of every exception this library raises, so a caller can catch
    anything snakestream raised without enumerating the leaves.

    Never raised directly - it exists to be caught, not thrown - and derives
    from Exception and nothing else. In particular not from ValueError: the
    same hierarchy covers IllegalStateException, which a reused stream raises,
    and a stream-reuse error is not a ValueError under any reading."""


class StreamBuildException(StreamException):
    pass


class IllegalStateException(StreamException):
    pass


# The message for the one TypeError this library raises rather than defining:
# comparator-contract requires a plain TypeError for a comparator returning a
# non-int, so there is no class to hang it on. Named here so all seven check
# sites - three in sort.py, four in comparator.py - word it identically; the
# check itself is inlined at each, being one `type(x) is not int` test that a
# function call could only wrap.
COMPARATOR_RESULT_TYPE_MESSAGE = "comparator must return an int (negative, zero, or positive), not {}"
