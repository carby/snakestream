from snakestream.stream import Stream

s: Stream[int] = Stream.of(1, 2, 3)
s.map(lambda n: n.upper())
