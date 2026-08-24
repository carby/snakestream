from snakestream import PROCESSES
from snakestream.execution import PROCESSES as EXECUTION_PROCESSES


def test_processes_exported_from_top_level_package() -> None:
    # then
    assert PROCESSES == EXECUTION_PROCESSES
