import snakestream
import snakestream.stream


def test_processes_is_not_exported_from_the_top_level_package() -> None:
    # then: PROCESSES is an import-time-bound fact, not a tunable lever -
    # assigning to it after RACING is built at import changes nothing a
    # pipeline does, so it carries no export
    assert not hasattr(snakestream, "PROCESSES")
    assert not hasattr(snakestream.stream, "PROCESSES")


def test_the_in_flight_bound_has_no_public_name() -> None:
    # given the whole exported surface
    exported = [name for name in dir(snakestream) if not name.startswith("_")]

    # then nothing reads or sets the racing executor's in-flight window: the
    # bound is a guarantee of finiteness, and the levers a caller is given for
    # its cost are unordered() and sequential(), not a number
    assert not [n for n in exported if any(w in n.lower() for w in ("flight", "ahead", "window"))]
    assert not hasattr(snakestream, "_in_flight")
    assert not hasattr(snakestream, "_IN_FLIGHT_PER_WORKER")

    # PROCESSES is the same kind of import-time-bound constant, and gets the
    # same answer: neither has a public name, for the same reason
    assert "PROCESSES" not in exported
