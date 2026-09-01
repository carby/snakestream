from snakestream import PROCESSES
from snakestream.execution import PROCESSES as EXECUTION_PROCESSES


def test_processes_exported_from_top_level_package() -> None:
    # then
    assert PROCESSES == EXECUTION_PROCESSES


def test_the_in_flight_bound_has_no_public_name() -> None:
    # given the whole exported surface
    import snakestream

    exported = [name for name in dir(snakestream) if not name.startswith("_")]

    # then nothing reads or sets the racing executor's in-flight window: the
    # bound is a guarantee of finiteness, and the levers a caller is given for
    # its cost are unordered() and sequential(), not a number
    assert not [n for n in exported if any(w in n.lower() for w in ("flight", "ahead", "window"))]
    assert not hasattr(snakestream, "_in_flight")
    assert not hasattr(snakestream, "_IN_FLIGHT_PER_WORKER")

    # and PROCESSES is unaffected - it names a concept with a Java counterpart
    assert "PROCESSES" in exported
