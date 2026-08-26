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
