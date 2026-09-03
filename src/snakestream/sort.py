import asyncio
from functools import cmp_to_key
from inspect import isawaitable
from operator import itemgetter
from typing import Any, cast
from collections.abc import Callable

from snakestream.callable_dispatch import is_async_callable
from snakestream.comparator import (
    ASYNC_COMPARATOR_MESSAGE,
    KeyComparator,
    NullPlacement,
    Segment,
)
from snakestream.exception import ComparatorContractException, StreamBuildException
from snakestream.type import AsyncComparator, Comparator


def _checked(comparator: Comparator) -> Callable[[Any, Any], int]:
    """A sync comparator wrapped so cmp_to_key cannot bypass the int contract.

    The test is one `type(sign) is not int`, written out here rather than
    called: cmp_to_key runs this O(n log n) times, and a function whose whole
    body is that test plus a raise gives back less than the indirection costs
    to read. Only the message is shared, from exception.py. Keeping the check
    at all is what makes the sync fast path 2.3x rather than 3.6x.
    """

    def compare(a: Any, b: Any) -> int:
        sign = comparator(a, b)
        if type(sign) is not int:
            raise ComparatorContractException(sign)
        return sign

    return compare


def _checked_segment_comparator(comparator: Comparator) -> Callable[[Any, Any], int]:
    """Like `_checked()`, for a comparator segment's column - built where
    that segment's column is built, per Decision 1. `is_async_callable`
    already rejected an async comparator segment at construction
    (`comparator.py`'s `_reject_async_comparator`); this catches the one
    shape that slips past that classifier - a plain `def __call__` that lies
    and returns a coroutine - and names the async rejection instead of the
    generic "must return an int", since that is the rule actually broken
    (Decision 3).
    """

    def compare(a: Any, b: Any) -> int:
        sign = comparator(a, b)
        if isawaitable(sign):
            raise StreamBuildException(ASYNC_COMPARATOR_MESSAGE)
        if type(sign) is not int:
            raise ComparatorContractException(sign)
        return sign

    return compare


async def sort(arr: list[Any], comparator: Comparator) -> list[Any]:
    """Sort by comparator, picking the algorithm the comparator allows.

    A sync comparator goes to list.sort() with cmp_to_key, i.e. Timsort in C;
    only an async one needs _merge_sort's hand-written merge with an await in
    its inner loop. Measured 2.1x on 20,000 floats here, 1.8x end-to-end
    through sorted() once the pipeline's own per-element cost is counted.

    The sync path cannot hand cmp_to_key the raw comparator: comparator-contract
    makes sorted() responsible for raising TypeError on a bool result, and a
    bool compares perfectly well under cmp_to_key, so an unchecked sort would
    silently produce a wrong order instead. Hence _checked().

    The choice between the two is made by one trial comparison, positively:
    an awaitable result takes _merge_sort, anything else takes list.sort. There
    is no `is_async_callable()` pre-test, because it could only ever
    over-approximate what the trial answers exactly - a comparator with a
    plain `def __call__` returning a coroutine classifies as sync
    (`_NullSafeComparator` is one), and list.sort offers no per-comparison
    await to catch that in, so the trial has to run anyway. Asking twice only
    bought skipping the trial for the comparators the classifier did
    recognize. The trial is awaited before rerouting so no coroutine is left
    un-awaited.

    So every comparator sort of two or more elements costs one extra
    comparator invocation - one call out of the n log n the sort itself makes,
    measured within noise on 20,000 floats for both paths. Nothing constrains
    the invocation count, and nothing could, since the two algorithms make
    different numbers of comparisons on the same input anyway. An async
    comparator's body does run once more than its comparisons alone require;
    for one doing I/O that is one extra round trip per sort.

    The trial's own result is deliberately not type-checked. Timsort's first
    comparison on a list of two or more is always element 1 against element 0,
    so `_checked()` sees the trial pair again immediately and raises the same
    TypeError; a check on the trial would only catch a comparator whose return
    *type* is asymmetric between (a, b) and (b, a).

    Returns the sorted list either way, though only _merge_sort builds a new
    one - list.sort is in place, and unifying the signature is worth more than
    saving the rebind.

    A list of fewer than two elements returns before any dispatch. It is the
    dispatcher's guard, not three defensive ones: no branch below is reachable
    with a shorter list, so `_sort_by_key()` needs no empty check and the trial
    comparison needs no `len(arr) > 1` of its own. _merge_sort keeps its
    `len(arr) <= 1` because that is its recursion base case, not an entry
    guard. It also settles what a one-element sort observes: no comparator
    invocation and no key extraction, matching Java, where TimSort returns
    before calling `Comparator.compare` and `comparing()`'s extractor is
    only reached from a comparison.
    """
    if len(arr) <= 1:
        return arr
    if isinstance(comparator, KeyComparator):
        return await _sort_by_key(arr, comparator.segments, comparator.nulls)
    trial = comparator(arr[0], arr[1])
    if isawaitable(trial):
        await trial
        return await _merge_sort(arr, cast("AsyncComparator", comparator))
    arr.sort(key=cmp_to_key(_checked(comparator)))
    return arr


def _interleave(arr: list[Any], values: list[Any]) -> list[Any]:
    """Re-align extracted values against `arr`, reinserting `None` for every
    element the extractor skipped - `values` holds one entry per non-`None`
    element of `arr`, in the same order."""
    it = iter(values)
    return [None if element is None else next(it) for element in arr]


async def _column(extractor: Callable[[Any], Any], arr: list[Any]) -> list[Any]:
    """Extract one segment's key for every element, concurrently across
    elements. No cmp_to_key, no _merge_sort, and no sign/bool validation -
    there is no comparator sign on this path, just a key.

    A `None` element yields `None` directly - the extractor is never invoked
    with it - so a null element presents as a null key in every segment (see
    this change's design.md, Decision 2). This holds whether or not the
    comparator tolerates nulls; a comparator that does not still ends up
    comparing `None` against a real key, and still raises `TypeError`, just
    from the sort rather than from the extractor.

    An async extractor's keys are gathered concurrently rather than awaited
    one at a time in a loop. Measured (design.md's open question, settled
    during implementation): an I/O-bound extractor (1ms sleep) sorting 1,000
    elements costs 1325ms sequential against 9ms gathered - concurrency is the
    whole point of an async key extractor, and a sequential loop was throwing
    it away. The one-time isawaitable safety net (a "sync" extractor whose
    plain def __call__ actually returns a coroutine) is caught on
    `results[0]` - the same shape as sort()'s own trial comparison - but the
    coroutine it produces joins the gather instead of being discarded, so it
    costs no extra invocation.
    """
    present = [element for element in arr if element is not None]
    if not present:
        return [None] * len(arr)
    if is_async_callable(extractor):
        return _interleave(arr, await asyncio.gather(*map(extractor, present)))
    results = [extractor(element) for element in present]
    if isawaitable(results[0]):
        return _interleave(arr, await asyncio.gather(*results))
    return _interleave(arr, results)


async def _segment_column(payload: Any, arr: list[Any]) -> list[Any]:
    """One segment's raw column, dispatching on payload shape (Decision 1/6):
    a plain callable is a key extractor and goes through `_column()`
    unchanged; a `(extractor, comparator)` pair - `extractor` possibly `None`
    for a bare comparator segment - extracts a column exactly as any other
    segment (or takes the elements themselves, unextracted, when there is no
    extractor - `_column()` is what makes an extractor-based column skip a
    `None` element, so a bare comparator segment's column takes the same
    elements every other segment's column would see) and then wraps each
    non-`None` entry through `cmp_to_key(_checked_segment_comparator(comparator))`,
    so it rides the same successive-pass sort as a key extractor's column: a
    `None` entry (null element, or for the two-argument form a null key)
    stays `None` for `_tolerant_column()` to place - a comparator segment has
    no key of its own to skip a `None` element for, so it presents as a null
    key exactly as an extractor segment's does (Decision 5) - and the wrapped
    entries compare in C via `reverse=True`/plain tuple order, one pass per
    segment, exactly as a natural key would.
    """
    if not isinstance(payload, tuple):
        return await _column(payload, arr)

    extractor, comparator = payload
    raw = await _column(extractor, arr) if extractor is not None else arr
    to_key = cmp_to_key(_checked_segment_comparator(comparator))
    return [None if v is None else to_key(v) for v in raw]


def _presence_markers(placement: NullPlacement) -> tuple[int, int]:
    """The leading tuple component a tolerant column's null/present values get,
    chosen so plain ascending tuple order already places nulls where
    `placement` says: `0 < 1`, so nulls-first gives `None` the `0` and a real
    key the `1`, and nulls-last swaps them."""
    return (0, 1) if placement is NullPlacement.FIRST else (1, 0)


def _tolerant_column(keys: list[Any], placement: NullPlacement) -> list[tuple[int, Any]]:
    """Wrap one column's keys as `(present, key)` per design Decision 3.
    Tuple comparison settles a null-vs-null pair on the leading component and
    never evaluates `None < None`; a column's own pass over `reverse=` then
    moves the nulls exactly as it moves any other key, which is what makes
    `reversed()` need no null-specific rule."""
    null_marker, present_marker = _presence_markers(placement)
    return [(null_marker, None) if key is None else (present_marker, key) for key in keys]


async def _sort_by_key(
    arr: list[Any], segments: tuple[Segment, ...], nulls: NullPlacement = NullPlacement.ABSENT
) -> list[Any]:
    """Decorate-sort-undecorate: extract every segment's key once per
    element, sort on the keys alone, undecorate.

    Sorting on the key(s) alone (list.sort(key=...) over the paired list, not
    a bare (key, element) tuple sort) means Timsort's stability gives
    encounter order for equal keys for free, with no tie-break index needed,
    and that elements are never compared - only their keys - so an element
    that does not itself support < still sorts fine as long as its key does.

    A single ascending segment - what every pre-chaining `comparing()` call
    produces - takes the `len(segments) == 1` fan-out branch and the
    `len(columns) == 1` lane: one column, no tuple build, no outer gather, so
    add-comparator-comparing's measured figures stand unchanged. A single
    descending segment (only reachable via `reversed()`) adds `reverse=True`,
    which is comparator negation exactly (see below) rather than a second code
    path.

    Two or more segments extract their columns concurrently with each other
    via `asyncio.gather` - not just concurrently within a column - so a chain
    of k async extractors over n elements has k*n extractions in flight
    rather than k sequential rounds of n; this is the capability's main
    reason to exist. The columns then sort as `sort-mixed-lane-by-successive-
    passes` (2026-09-02) settled it: one `sorted()` on the least significant
    column, then one `.sort()` per remaining column in decreasing
    significance, each pass carrying that column's own `reverse=`. CPython
    guarantees `list.sort()` is stable and that `reverse=True` is stable in
    the strong sense - it negates comparisons rather than reversing the
    result - so a run of stable passes, least significant first, composes
    into exactly the lexicographic multi-key ordering a single tuple sort
    would, direction per column included. Every pass compares bare keys in C;
    no wrapper object is ever built.

    This replaces the three lanes an earlier version of this function hand-
    built (all-ascending tuple sort, all-descending `reverse=True`, and a
    mixed lane wrapping descending columns in a `_Descending` shim so tuple
    comparison would treat them as negated) with the one loop above, for
    every chain of two or more segments regardless of direction - see that
    change's design.md for the alternatives it priced and declined.

    Measured, 20,000 rows: a 2-segment mixed-direction chain that cost ~35ms
    under the old wrapper lane costs ~6ms here, and an 8-segment mixed chain
    that cost ~56ms costs ~20ms - the wrapper's Python-level `__lt__` per
    tied pair is gone. A uniform (single-direction) chain trades the old
    lane's one short-circuiting tuple comparison for k full passes, so it
    wins at two and three segments and loses from five on: the measured
    crossover on this machine sits between four and five segments, where a
    tuple comparison's ability to stop at the first unequal component starts
    to beat k passes each visiting every row. A five-or-more-segment
    `then_comparing()` chain is not a shape this library has seen in the
    wild.

    A `nulls_first`/`nulls_last` comparator wraps each column's keys as
    `(present, key)` tuples (see `_tolerant_column()`) before this function's
    passes run, so a tolerant chain pays a per-column 2-tuple comparison
    instead of a bare-value one - orthogonal to, and unaffected by, the
    lane rewrite above.
    """
    if len(segments) == 1:
        columns = [await _segment_column(segments[0][0], arr)]
    else:
        columns = await asyncio.gather(*(_segment_column(payload, arr) for payload, _ in segments))
    if nulls is not NullPlacement.ABSENT:
        columns = [_tolerant_column(column, nulls) for column in columns]
    directions = [descending for _, descending in segments]

    if len(columns) == 1:
        paired = sorted(zip(columns[0], arr, strict=True), key=itemgetter(0), reverse=directions[0])
        return list(map(itemgetter(-1), paired))

    last = len(columns) - 1
    paired = sorted(zip(*columns, arr, strict=True), key=itemgetter(last), reverse=directions[last])
    for i in reversed(range(last)):
        paired.sort(key=itemgetter(i), reverse=directions[i])
    return list(map(itemgetter(-1), paired))


async def _merge_sort(arr: list[Any], comparator: AsyncComparator) -> list[Any]:
    # Reached only for a comparator sort() has already established returns
    # awaitables, so there is no classification left to make or share here.
    if len(arr) <= 1:
        return arr

    middle = len(arr) // 2
    left = await _merge_sort(arr[:middle], comparator)
    right = await _merge_sort(arr[middle:], comparator)

    return await _merge(left, right, comparator)


async def _merge(left: list[Any], right: list[Any], comparator: AsyncComparator) -> list[Any]:
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        sign = await comparator(left[i], right[j])
        if type(sign) is not int:
            raise ComparatorContractException(sign)
        if sign <= 0:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result
