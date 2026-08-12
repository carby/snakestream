from __future__ import annotations

from typing import Generic

from snakestream.stream import Stream
from snakestream.type import T


class StreamBuilder(Generic[T]):
    def __init__(self) -> None:
        self._elements: list[T] = []

    def add(self, element: T) -> StreamBuilder[T]:
        self.accept(element)
        return self

    def accept(self, element: T) -> None:
        self._elements.append(element)

    def build(self) -> Stream[T]:
        return Stream(self._elements)
