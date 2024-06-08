from typing import List

from snakestream.stream import Stream
from snakestream.type import T


class StreamBuilder():
    def __init__(self) -> None:
        self._elements: List[T] = []

    def add(self, element: T) -> 'StreamBuilder':
        self.accept(element)
        return self

    def accept(self, element: T) -> None:
        self._elements.append(element)

    def build(self) -> 'Stream':
        return Stream(self._elements)
