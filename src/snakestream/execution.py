"""How a stream runs, as a value rather than as the stream's type.

Executor is the protocol two values implement: SEQUENTIAL, over the primitives
in pipeline.py, and FORK_JOIN, over the parallel batch machinery in
fork_join.py. Neither this module's Executor.value() generic form nor
_Sequential's override does anything but call into one of those two modules —
_Sequential.elements() picks stream_through(), _ForkJoin.elements() picks
fork_join_through(); _Sequential.value() is the one asymmetry in the protocol,
overriding the generic drain(elements(...), terminal) with feed_through()
because composing-then-draining measured far more expensive per element (see
its own docstring for the figures); _ForkJoin.value() has a second override,
delegating to fork_join_partitioned() where the terminal partitions and
nothing in the chain needs a global view.

A stream consults its executor in exactly two places: iterator() and
_evaluate() (stream.py). Both operations carry the consumer's OrderDemand
declaration alongside the chain and the source — see ordering.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar
from collections.abc import AsyncGenerator

from snakestream.fork_join import WORKERS, fork_join_partitioned, fork_join_through
from snakestream.ordering import OrderDemand, split_point
from snakestream.pipeline import drain, feed_through, stream_through
from snakestream.sink import Op, TerminalSink


# --- the executors ------------------------------------------------------


class Executor(ABC):
    """How a stream runs, as a value rather than as the stream's type. Two
    operations: one producing the chain's elements as a generator, one driving
    the chain into a terminal sink.

    Both take `demand`, the consumer's declaration of what it asks of
    encounter order. It is a second axis alongside which executor a terminal
    names: the executor decides *how* the chain runs, this decides whether the
    executor owes it encounter order. elements()' consumer can always tell - it
    hands out raw elements - so its callers pass IF_ORDERED; a terminal answers
    for itself, and most of them do not care.

    It sits on the protocol rather than being read off the terminal sink
    because elements() has no terminal sink to read. It is an OrderDemand
    rather than a bool because find_first() asks unconditionally, which a bool
    cannot distinguish from asking where the pipeline happens to be ordered -
    see OrderDemand."""

    is_parallel: ClassVar[bool]

    @abstractmethod
    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator: ...

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """The general form: compose, then drain into the terminal. Correct for
        any executor; _ForkJoin uses it unchanged."""
        return await drain(self.elements(chain, source, demand), terminal)


class _Sequential(Executor):
    is_parallel = False

    # demand is accepted and ignored throughout: a single ordered pass
    # delivers in encounter order whether or not anyone is looking. The
    # parameter is on the protocol because the *racing* executor needs it, and
    # a caller must be able to state the demand without knowing which executor
    # will read it.

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return stream_through(chain, source)

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """Overrides the general form with the fused push, which is the one
        asymmetry in this protocol and is here on measurement, not taste:
        composing and then draining costs +125% per element on count() and
        +112% on reduce() (Python 3.14.5, 20,000 elements, no intermediate
        chain, best of 5). Removing the generator between the last sink and the
        terminal removes an accept, a buffer append, a truthiness check, a
        yield across the async-generator boundary and a list clear, per
        element. Results are identical to the general form."""
        return await feed_through(chain, source, terminal)


class _ForkJoin(Executor):
    is_parallel = True

    __slots__ = ("workers",)

    def __init__(self, workers: int) -> None:
        self.workers = workers

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return fork_join_through(chain, source, self.workers, demand)

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """Where the terminal partitions and nothing in the chain needs a
        global view, accumulate each batch into its own container on its own
        worker thread and merge them into `terminal` (fork_join_partitioned()).
        Otherwise fall through to the generic form unchanged - a terminal
        that does not opt in (can_partition() False) or a chain containing an
        op split_point() would have to see whole (sorted(), or limit/skip/
        distinct on an ordered pipeline) gets exactly today's behaviour,
        because a per-batch terminal cannot give such an op the global view
        it needs (design decision 1, make-combiners-live: the protocol adds
        a second partitioning path, it does not touch elements() or the
        split machinery that already handles those ops).

        The terminal's own OrderDemand plays no part in that check - unlike
        elements()'s split, which inserts a reordering pass before handing
        elements to a caller. A partitioned merge is already in encounter
        order by construction (batches are pulled and merged in sequence,
        design decision 2), so there is nothing for a terminal's demand to
        buy here; only an *op* needing a global view (sorted(), or
        limit/skip/distinct on an ordered pipeline) can force the fallback.
        OrderDemand.NONE passed to split_point() disables its third,
        terminal-driven clause and leaves the first two untouched."""
        if terminal.can_partition() and split_point(chain, OrderDemand.NONE, True) is None:
            return await fork_join_partitioned(chain, source, self.workers, terminal)
        return await super().value(chain, source, terminal, demand)


SEQUENTIAL = _Sequential()
FORK_JOIN = _ForkJoin(WORKERS)
