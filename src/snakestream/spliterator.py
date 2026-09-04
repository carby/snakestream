"""`Spliterator[T]`: Java's parallel-decomposition iterator, ported with its
full method surface — `try_advance`, `try_split`, `estimate_size`,
`characteristics`, `for_each_remaining` — plus `Characteristics`, the
`ORDERED`/`SIZED` flags it reports. `Stream.spliterator()` builds one over a
stream's composed chain; see `stream.py`.

`try_split()` always drains a bounded batch rather than index-splitting, even
over a source `estimate_size()` reports as `SIZED`: by the time a stream
composes its chain into elements, the source is already an `AsyncGenerator`
with no random access, so this is the one strategy available - the same one
Java's `Spliterators.IteratorSpliterator` falls back to for an unsized
source (see design.md, Context)."""

from __future__ import annotations

from enum import Enum, auto
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable, AsyncGenerator, AsyncIterator

from snakestream.callable_dispatch import is_async_callable, maybe_await
from snakestream.type import Consumer

# Java's IteratorSpliterator starts at 1024 and grows by 1024 per split, a
# curve shaped for its recursive fork-join pool. The split here is flat - one
# batch per worker, not a recursive halving - so the growth has nothing to
# act on; a fixed default is the starting point, and tuning it is a
# measurement (fork-join-executor-and-spliterator, task 7.2), not an
# assumption made here.
BATCH_SIZE = 1024


class Characteristics(Enum):
    """The two flags `Spliterator.characteristics()` reports, at minimum, per
    the `stream-spliterator` spec. Java packs a wider set - `SORTED`,
    `DISTINCT`, `NONNULL`, `IMMUTABLE`, `CONCURRENT`, `SUBSIZED` among them -
    into a bitmask on the interface itself; this ports the two this library
    can state truthfully today rather than the whole set."""

    ORDERED = auto()
    SIZED = auto()


async def batch(source: AsyncIterator[Any], limit: int) -> list[Any]:
    """Drain at most `limit` elements from `source`. `try_split()`'s own
    pull, and `execution.py`'s fork-join executor's - the same bounded-drain
    primitive either way, since fork-join batches the raw source exactly the
    way `try_split()` batches a composed one. Fewer than `limit` items back
    means the source is now exhausted, read off `len(items)` rather than a
    second signal."""
    items = []
    for _ in range(limit):
        try:
            items.append(await anext(source))
        except StopAsyncIteration:
            break
    return items


async def _replay(items: list[Any]) -> AsyncGenerator[Any]:
    for item in items:
        yield item


class Spliterator[T]:
    """A decomposable, awaitable traversal over a composed stream's elements.
    Contiguous decomposition is the load-bearing property `try_split()`
    guarantees - see its own docstring - which is what lets two partial
    results be combined on associativity alone."""

    __slots__ = ("_ordered", "_size", "_source")

    def __init__(self, source: AsyncGenerator[T], *, ordered: bool, size: int | None) -> None:
        self._source = source
        self._ordered = ordered
        # None is the distinguished "unknown" value the stream-spliterator
        # spec asks estimate_size() to return - never 0 and never a guess.
        self._size = size

    async def try_advance(self, action: Consumer[T]) -> bool:
        try:
            item = await anext(self._source)
        except StopAsyncIteration:
            return False
        await maybe_await(action, item)
        if self._size is not None:
            self._size -= 1
        return True

    async def try_split(self) -> Spliterator[T] | None:
        """Drain up to `BATCH_SIZE` elements into the returned spliterator,
        leaving this one positioned over whatever remains. `None` once this
        spliterator has nothing left to give away - the batch drains to
        empty - which is what makes repeated splitting terminate on a finite
        source: each call either shrinks the remainder or the remainder was
        already empty."""
        items = await batch(self._source, BATCH_SIZE)
        if not items:
            return None
        split_size: int | None = None
        if self._size is not None:
            split_size = len(items)
            self._size -= len(items)
        return Spliterator(_replay(items), ordered=self._ordered, size=split_size)

    def estimate_size(self) -> int | None:
        return self._size

    def characteristics(self) -> frozenset[Characteristics]:
        flags = set()
        if self._ordered:
            flags.add(Characteristics.ORDERED)
        if self._size is not None:
            flags.add(Characteristics.SIZED)
        return frozenset(flags)

    async def for_each_remaining(self, action: Consumer[T]) -> None:
        # canonical per-composition classify-once shape (callable_dispatch.py)
        is_async = is_async_callable(action)
        checked = False
        async for item in self._source:
            r = action(item)
            if is_async:
                await cast("Awaitable[None]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    await r
        self._size = 0
