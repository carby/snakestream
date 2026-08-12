from snakestream.stream import Stream
from snakestream.stream_builder import StreamBuilder


def _use_map(s: Stream[int]) -> Stream[str]:
    return s.map(str)


def _use_filter(s: Stream[int]) -> Stream[int]:
    return s.filter(lambda n: n > 0)


def _use_builder() -> Stream[int]:
    builder: StreamBuilder[int] = StreamBuilder()
    return builder.add(1).add(2).build()
