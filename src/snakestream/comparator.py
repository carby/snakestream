from typing import Any, cast

from snakestream.callable_dispatch import is_async_callable
from snakestream.type import KeyExtractor


def check_comparator_result_type(value: int) -> None:
    if type(value) is not int:
        raise TypeError(f"comparator must return an int (negative, zero, or positive), not {type(value).__name__}")


def is_new_extremum(sign: int, asc: bool) -> bool:
    """Whether an element that compared as `sign` against the currently-held
    extremum should displace it. The one home for the rule Stream.min()/max()
    and the min_by()/max_by() collectors both implement.

    comparator(element, found): negative if element orders before found,
    positive if after. found - the earlier element - is kept on a tie, which is
    what makes both forms first-of-tied-wins.

    "Earlier" means earlier in *encounter order*, not earlier to arrive. This
    function only ever sees the order its caller was fed, so the guarantee is
    the caller's to arrange: Stream.min()/max() declare observes_order=True and
    min_by()/max_by() decline Characteristics.UNORDERED, so both take the
    racing executor's delivery barrier and both agree with the sequential
    answer. On a pipeline declared unordered() neither takes it and which of
    two tied elements wins is unspecified, matching Java - see
    comparator-contract, which states the rule for sorted() too, as stability.

    Sync, and takes an already-awaited sign: it sits on the per-element path of
    both callers, so it replaces their existing check_comparator_result_type()
    call rather than adding a second one. The type test is inlined and only the
    raising path calls out, which keeps the success path at exactly the one
    call per element it cost before - delegating the check measured ~5%, and
    routing these terminals through a Collector instead cost +26% (see this
    change's design.md).
    """
    if type(sign) is not int:
        check_comparator_result_type(sign)
    return sign < 0 if asc else sign > 0


Segment = tuple[KeyExtractor, bool]


class KeyComparator:
    """The `Comparator` a `comparing()` call returns.

    Exposes `segments` - an ordered tuple of `(key_extractor, descending)`
    pairs - as a plain attribute so sort() can unwrap it and extract each
    segment's key once, rather than the per-comparison cost __call__ below
    pays; __call__ exists so this is still a working Comparator for any
    consumer - min(), max(), min_by(), max_by() - that does not know to look
    for the attribute.

    Each segment's extractor is classified sync/async independently
    (`callable-dispatch`), once here at construction rather than per element
    or per comparison.
    """

    def __init__(self, segments: tuple[Segment, ...]) -> None:
        self.segments = segments
        self._is_async = tuple(is_async_callable(extractor) for extractor, _ in segments)
        self._any_async = any(self._is_async)

    def then_comparing(self, other: "KeyExtractor | KeyComparator") -> "KeyComparator":
        """Append a tie-break ordering, matching Java's
        `Comparator.thenComparing`. `other` may be a bare key extractor,
        contributing one ascending segment, or another `KeyComparator`, whose
        whole segment list - directions intact - is spliced in. Returns a new
        `KeyComparator`; the receiver is unchanged.
        """
        if isinstance(other, KeyComparator):
            return KeyComparator(self.segments + other.segments)
        return KeyComparator((*self.segments, (other, False)))

    def reversed(self) -> "KeyComparator":
        """Negate the whole ordering, matching Java's `Comparator.reversed`.

        Flips every segment's direction rather than wrapping __call__'s
        result, because flipping each component of a lexicographic order is
        the same as negating the composite - which is why calling this before
        or after `then_comparing()` reproduces Java's two distinct outcomes
        with one implementation. Returns a new `KeyComparator`; the receiver
        is unchanged.
        """
        return KeyComparator(tuple((extractor, not descending) for extractor, descending in self.segments))

    def __call__(self, a: Any, b: Any) -> Any:
        if self._any_async:
            return self._compare_async(a, b)
        return self._compare_sync(a, b)

    def _compare_sync(self, a: Any, b: Any) -> int:
        for extractor, descending in self.segments:
            # not self._any_async is what makes this branch reachable, so
            # every segment's sync arm is the one that ran - Any, not
            # Awaitable[Any].
            ka = cast("Any", extractor(a))
            kb = cast("Any", extractor(b))
            sign = (ka > kb) - (ka < kb)
            if descending:
                sign = -sign
            if sign != 0:
                return sign
        return 0

    async def _compare_async(self, a: Any, b: Any) -> int:
        for (extractor, descending), is_async in zip(self.segments, self._is_async, strict=True):
            if is_async:
                ka = await extractor(a)
                kb = await extractor(b)
            else:
                ka = cast("Any", extractor(a))
                kb = cast("Any", extractor(b))
            sign = (ka > kb) - (ka < kb)
            if descending:
                sign = -sign
            if sign != 0:
                return sign
        return 0


def comparing(key_extractor: KeyExtractor) -> KeyComparator:
    """Build a Comparator that orders by an extracted key, matching Java's
    `Comparator.comparing(keyExtractor)`.

    Returns an object rather than a plain `lambda a, b: ...` closure, because a
    closure would call key_extractor twice per comparison - O(n log n) times,
    which for an async key extractor is `2n log n` awaits. sort() recognizes
    this object (via its `segments` attribute) and instead extracts each
    segment's key exactly once and sorts on the keys directly, which is the
    whole reason this capability exists - see this change's proposal.md for
    the measured win. Every other comparator-consuming operation - min(),
    max(), min_by(), max_by() - still works via the ordinary __call__ path
    above, just without that fast path.

    key_extractor may be sync or async, like every other user-supplied
    callable in this library.

    The result composes: `.then_comparing(other)` appends a tie-break
    ordering - a bare key extractor or another `KeyComparator`, chainable to
    any depth - and `.reversed()` negates the ordering built so far. Reverse
    before chaining to flip only that segment; reverse after to flip the
    whole composite. A hand-written tuple key
    (`comparing(lambda x: (x.last, x.first))`) is still the better answer for
    a sync, single-direction, multi-key ordering: one call per element, no
    wrapper object, no gather. Chaining earns its keep once an extractor is
    async - a tuple literal cannot await, and an `async def` equivalent
    resolves its keys in sequence rather than concurrently - or once directions
    mix.
    """
    return KeyComparator(((key_extractor, False),))
