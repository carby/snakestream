import snakestream
import snakestream.execution
import snakestream.stream


def test_workers_is_not_exported_from_the_top_level_package() -> None:
    # then: WORKERS is an import-time-bound fact, not a tunable lever -
    # assigning to it after FORK_JOIN is built at import changes nothing a
    # pipeline does, so it carries no export
    assert not hasattr(snakestream, "WORKERS")
    assert not hasattr(snakestream.stream, "WORKERS")

    # and the old name is gone outright, not aliased
    assert not hasattr(snakestream.execution, "PROCESSES")


def test_the_read_ahead_bound_has_no_public_name() -> None:
    # given the whole exported surface
    exported = [name for name in dir(snakestream) if not name.startswith("_")]

    # then nothing reads or sets fork/join's first-round batch size: the
    # bound is a guarantee of finiteness, and the levers a caller is given for
    # its cost are unordered() and sequential(), not a number
    assert not [n for n in exported if any(w in n.lower() for w in ("flight", "ahead", "window", "batch"))]
    assert not hasattr(snakestream, "_FIRST_BATCH_SIZE")
    assert not hasattr(snakestream, "_in_flight")
    assert not hasattr(snakestream, "_IN_FLIGHT_PER_WORKER")

    # WORKERS is the same kind of import-time-bound constant, and gets the
    # same answer: neither has a public name, for the same reason
    assert "WORKERS" not in exported
