"""The encounter-order model: the vocabulary, the fold and the split search,
and nothing else. Ordering states what an op does to the pipeline's
encounter-order characteristic; OrderDemand states what a terminal asks of
it — the two enums are deliberately the same shape read from opposite ends,
and OrderDemand's and split_point()'s docstrings both print the table that
pairs them. is_ordered() is the fold that answers the characteristic for a
chain; split_point() is the search that answers where a racing executor's
delivery barrier goes.

Reads ops structurally: is_ordered() and split_point() consult only
op.ordering and op.order_sensitive, and neither constructs, links, drives, nor
awaits one. Op is imported for typing only, under TYPE_CHECKING, so the
sink -> ordering edge stays one-directional — sink.py imports Ordering here at
runtime, and this module never imports sink.py at runtime."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakestream.sink import Op


class Ordering(Enum):
    """What an op does to the pipeline's encounter-order characteristic — the
    three things Java's StreamOpFlag can say about a flag at a given stage:
    PRESERVE it from upstream, CLEAR it, or SET it.

    Java encodes this as two bits per flag in a packed int, folded down the
    stage list by combineOpFlags(). We port the meaning, not the encoding: it
    packs bits because it carries five characteristics (ORDERED, SIZED, SORTED,
    DISTINCT, SHORT_CIRCUIT) through a fold that runs on every stage, and we
    carry one. A three-member enum says what a two-bit field says, and says it
    in words."""

    PRESERVE = auto()
    CLEAR = auto()
    SET = auto()


class OrderDemand(Enum):
    """What a terminal asks of the pipeline's encounter-order characteristic,
    where sink.Ordering says what an *op* does to it. The pair is the whole
    input to split_point(), and the two enums are deliberately the same shape
    read from opposite ends.

    Three values because a demand can be unconditional or conditional, and a
    bool cannot say the first. The clauses line up one for one:

        op in the chain          the terminal
        Ordering.SET             ALWAYS       unconditional
        order_sensitive          IF_ORDERED   only where the pipeline is ordered
        (neither)                NONE         no demand, and pays nothing

    Java has no name to borrow here. Its terminals answer this question by
    choosing a task class - FindTask against ForEachTask - so there is no
    counterpart to be at parity with, and the name is built to sit beside
    Ordering instead.

    ALWAYS has exactly one holder, find_first(), and the stream-execution-model
    capability says so as a requirement: a demand that survives unordered() is
    a claim no other terminal in Java or here makes."""

    NONE = auto()
    IF_ORDERED = auto()
    ALWAYS = auto()


def is_ordered(chain: list[Op], upto: int | None = None, initial: bool = True) -> bool:
    """Whether the pipeline carries an encounter-order requirement at position
    `upto` (the end of the chain when omitted): the three-valued fold over the
    ops before it, seeded with `initial`. Java's combineOpFlags() folds the same
    answer down its stage list; here the fold is the whole of it, because there
    is one characteristic rather than five.

    Never cached onto anything. A denormalised copy of a chain property is
    exactly what let unordered() apply to a whole pipeline regardless of where
    it was written. Chains are single digits long, and this runs at most once
    per terminal plus once per composition under the racing executor.

    The `upto` form is what the racing executor's split search needs: an op is a
    split point only if the pipeline is ordered *at its own position*, which is
    the fold over everything queued before it.

    `initial` is what a *suffix* needs. The racing executor splits a chain at a
    barrier and re-enters itself on what follows, so it folds over a list of ops
    that is not the whole pipeline. Seeding with True there would read
    `.sorted(c).unordered().map(f)`'s suffix as ordered and reinstate a
    requirement the caller cleared two ops earlier; the seed carries the answer
    across the split. A full chain starts from True because a source is ordered
    until something says otherwise.

    A free function over a chain rather than a Stream method: the fold is a
    property of a list of Ops, not of the stream that built them, and both
    split_point() and Stream._is_ordered() read it as that."""
    ordered = initial
    for op in chain[:upto] if upto is not None else chain:
        if op.ordering is not Ordering.PRESERVE:
            ordered = op.ordering is Ordering.SET
    return ordered


def split_point(chain: list[Op], demand: OrderDemand, ordered_in: bool) -> int | None:
    """The index at which encounter order has to be restored, or None when it
    never does and the chain can race end-to-end.

    Two callers, three clauses. An *operation* needs order restored before it,
    per the racing-encounter-order capability:

    - an op that SETs the ordering characteristic — `sorted()` — splits
      wherever it sits, regardless of the characteristic upstream of it. A sort
      claims its output is ordered, so it must see the whole stream to make
      that claim true. `.unordered().sorted()` is unordered at the sort's own
      position and the second clause alone would leave it in the raced head,
      sorting each branch's subset; Java's SortedOps contributes IS_ORDERED for
      the same reason, read from the other side.
    - an order_sensitive op — limit, skip, distinct — at a position where the
      fold reports the pipeline ordered. Where it does not, the caller has said
      any answer will do and the cheap order-blind path is correct.

    The *terminal* needs it restored before delivery, which is the third
    clause and is why this returns `len(chain)` rather than an op's index: a
    split at the end means every op still runs in parallel and only the
    handing over is ordered (though under fork/join, where contiguous
    batches never scramble it in the first place, that handing-over is
    already ordered before the split is even asked for). Expressing it as a
    split is what lets one mechanism serve both — the executor runs the same
    head/barrier/tail shape either way, with an empty tail here.

    That third clause is the two op clauses again, one level up, which is what
    OrderDemand's three values are for:

        op in the chain          the terminal
        Ordering.SET             ALWAYS       splits whatever is upstream
        order_sensitive          IF_ORDERED   splits only where ordered here

    ALWAYS is find_first()'s, and nothing else's. It reads as a contradiction
    on a pipeline the caller declared unordered() and is not one: the barrier
    can always restore encounter order, because a split's head still pulls
    contiguous batches in source order regardless of unordered() — that
    property was never conditional on the ordering characteristic, only its
    *delivery* is — and unordered() clears the *requirement* to honour it,
    never the ability. So a demand that survives the clearing is coherent, and
    it is the one Java's FindOp makes when mustFindFirst is fixed at
    construction and never consults the upstream ORDERED flag.

    The first hit wins: there is at most one barrier per composition, and
    everything downstream of it already arrives in order.

    `ordered_in` seeds the fold, because a resumed tail is a chain suffix whose
    ordering was decided by ops that are no longer in the list; see
    is_ordered(). An ALWAYS demand crossing that split keeps splitting: a
    resumed suffix that clears the characteristic still owes find_first() its
    delivery barrier, where an IF_ORDERED one is correctly released by it."""
    for i, op in enumerate(chain):
        if op.ordering is Ordering.SET or (op.order_sensitive and is_ordered(chain, i, ordered_in)):
            return i
    if demand is OrderDemand.ALWAYS or (demand is OrderDemand.IF_ORDERED and is_ordered(chain, initial=ordered_in)):
        return len(chain)
    return None
