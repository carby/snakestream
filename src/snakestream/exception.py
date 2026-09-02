from typing import Any


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


class ComparatorContractException(StreamBuildException, TypeError):
    """Raised where a user-supplied Comparator returns a value that is not
    an int (comparator-contract's "Comparators must not return bool", which
    also covers any other non-int return).

    Mixes in TypeError, not just StreamException, so every existing
    `except TypeError` around a comparator-consuming operation keeps
    catching exactly what it caught before this leaf existed - the base
    class stays narrow (exception-hierarchy forbids it deriving from any
    built-in but Exception) precisely so a leaf remains free to be specific
    about the one fault it reports, and this fault genuinely is a type error.

    Based on StreamBuildException rather than the bare StreamException:
    `_checked_segment_comparator` already raises StreamBuildException two
    lines above this, for an async comparator segment - the same class of
    fault, "the comparator you supplied cannot be used". A caller wanting to
    handle one almost certainly wants to handle the other under one except
    clause. "Build" names the fault - something wrong with how the pipeline
    was constructed - not the moment it is discovered, which here is mid-sort
    because a comparator's shape can only be learned by invoking it.

    Takes the offending value, not a message: the wording belongs to the one
    class that carries it, so the six raise sites - three in sort.py, three in
    comparator.py - say `raise ComparatorContractException(sign)` and cannot
    word it differently from one another. The check itself stays inlined at
    each, being one `type(x) is not int` test that a function call could only
    wrap.

    Keeping the value in args and rendering in __str__, rather than formatting
    in __init__, is what makes the exception survive a round trip:
    BaseException.__reduce__ replays args through __init__, so an instance
    built from a finished message would come back reporting the type of the
    message ("not str") instead of the type of the value.
    """

    def __init__(self, value: Any) -> None:
        super().__init__(value)

    def __str__(self) -> str:
        return _RESULT_TYPE_MESSAGE.format(type(self.args[0]).__name__)


_RESULT_TYPE_MESSAGE = "comparator must return an int (negative, zero, or positive), not {}"
