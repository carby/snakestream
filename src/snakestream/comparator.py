from enum import Enum, auto
from typing import Any, TypeVar, cast, overload

from snakestream.callable_dispatch import is_async_callable
from snakestream.type import Comparator, KeyExtractor

T = TypeVar("T")


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
    the caller's to arrange: Stream.min()/max() declare OrderDemand.IF_ORDERED and
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


class NullPlacement(Enum):
    """Where `None` sorts relative to non-`None` values, per `KeyComparator`.

    `ABSENT` is what every `comparing()` call constructs before `nulls_first`/
    `nulls_last` touch it - the ordinary, intolerant comparator that raises on
    `None` exactly as it always has. It is a property of the whole comparator
    rather than of one segment: Java's `nullsFirst`/`nullsLast` wrap a whole
    `Comparator`, and `then_comparing()` carries the field onto its result, so
    a tie-break appended to a tolerant chain is tolerant too (see this
    change's design.md, Decision 1).
    """

    ABSENT = auto()
    FIRST = auto()
    LAST = auto()


def _null_sign(a_is_none: bool, placement: NullPlacement) -> int:
    """The sign a null-vs-non-null pair contributes, before any descending
    negation. `a_is_none` picks which side is `None`; the other side, by the
    caller's contract, is not (a "both None" pair falls through to the next
    segment instead of calling this)."""
    at_front = -1 if placement is NullPlacement.FIRST else 1
    return at_front if a_is_none else -at_front


def _constant_key(_: Any) -> int:
    """The key extractor `nulls_first()`/`nulls_last()` build a `KeyComparator`
    over when given nothing to wrap, matching Java's `nullsFirst(null)`: every
    non-`None` element is equivalent to every other, so the constant never
    distinguishes them."""
    return 0


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

    `nulls` defaults to `NullPlacement.ABSENT`, so every `comparing(f)` call
    with no `nulls_first`/`nulls_last` in its history constructs exactly what
    it constructed before that factory pair existed.
    """

    def __init__(self, segments: tuple[Segment, ...], nulls: NullPlacement = NullPlacement.ABSENT) -> None:
        self.segments = segments
        self.nulls = nulls
        self._is_async = tuple(is_async_callable(extractor) for extractor, _ in segments)
        self._any_async = any(self._is_async)

    def then_comparing(self, other: "KeyExtractor | KeyComparator") -> "KeyComparator":
        """Append a tie-break ordering, matching Java's
        `Comparator.thenComparing`. `other` may be a bare key extractor,
        contributing one ascending segment, or another `KeyComparator`, whose
        whole segment list - directions intact - is spliced in. Returns a new
        `KeyComparator`; the receiver is unchanged.

        Carries the receiver's null tolerance onto the result. This is a
        deliberate divergence from Java, where
        `nullsFirst(comparing(a)).thenComparing(b)` calls `b` on the elements
        `a` already ordered as null - two nulls compare equal under `a`, so
        `b` sees them - and throws `NullPointerException`. Inheriting the
        field is the only rule under which a null key falling through to a
        tie-break segment terminates rather than raising.
        """
        if isinstance(other, KeyComparator):
            return KeyComparator(self.segments + other.segments, self.nulls)
        return KeyComparator((*self.segments, (other, False)), self.nulls)

    def reversed(self) -> "KeyComparator":
        """Negate the whole ordering, matching Java's `Comparator.reversed`.

        Flips every segment's direction rather than wrapping __call__'s
        result, because flipping each component of a lexicographic order is
        the same as negating the composite - which is why calling this before
        or after `then_comparing()` reproduces Java's two distinct outcomes
        with one implementation. Returns a new `KeyComparator`; the receiver
        is unchanged.

        No null-specific rule is needed here: null tolerance already flows
        through the same per-segment direction each key participates in
        (`_compare_sync`/`_compare_async` negate a null sign exactly as they
        negate a real one, and `sort.py`'s tolerant column does the same via
        tuple reversal), so flipping every segment's direction already moves
        the nulls to the other end - matching Java's
        `nullsFirst(c).reversed() == nullsLast(c)`.
        """
        return KeyComparator(tuple((extractor, not descending) for extractor, descending in self.segments), self.nulls)

    def __call__(self, a: Any, b: Any) -> Any:
        if self._any_async:
            return self._compare_async(a, b)
        return self._compare_sync(a, b)

    def _compare_sync(self, a: Any, b: Any) -> int:
        nulls = self.nulls
        for extractor, descending in self.segments:
            # not self._any_async is what makes this branch reachable, so
            # every segment's sync arm is the one that ran - Any, not
            # Awaitable[Any].
            if nulls is NullPlacement.ABSENT:
                ka = cast("Any", extractor(a))
                kb = cast("Any", extractor(b))
                sign = (ka > kb) - (ka < kb)
            else:
                ka = None if a is None else cast("Any", extractor(a))
                kb = None if b is None else cast("Any", extractor(b))
                if ka is None or kb is None:
                    if ka is None and kb is None:
                        continue
                    sign = _null_sign(ka is None, nulls)
                else:
                    sign = (ka > kb) - (ka < kb)
            if descending:
                sign = -sign
            if sign != 0:
                return sign
        return 0

    async def _compare_async(self, a: Any, b: Any) -> int:
        nulls = self.nulls
        for (extractor, descending), is_async in zip(self.segments, self._is_async, strict=True):
            if nulls is NullPlacement.ABSENT:
                if is_async:
                    ka = await extractor(a)
                    kb = await extractor(b)
                else:
                    ka = cast("Any", extractor(a))
                    kb = cast("Any", extractor(b))
                sign = (ka > kb) - (ka < kb)
            else:
                if is_async:
                    ka = None if a is None else await extractor(a)
                    kb = None if b is None else await extractor(b)
                else:
                    ka = None if a is None else cast("Any", extractor(a))
                    kb = None if b is None else cast("Any", extractor(b))
                if ka is None or kb is None:
                    if ka is None and kb is None:
                        continue
                    sign = _null_sign(ka is None, nulls)
                else:
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


class _NullsComparator:
    """The `Comparator` `nulls_first()`/`nulls_last()` return when wrapping
    anything other than a `KeyComparator` - a hand-written comparator, with no
    keys for a fast-path column to be built from. `None` is checked for and
    delegates otherwise, matching Java's `nullsFirst`/`nullsLast` over a bare
    `Comparator`.

    `comparator` is classified sync/async once here at construction via
    `is_async_callable`, per `callable-dispatch`, rather than per comparison.
    """

    def __init__(self, comparator: Comparator, placement: NullPlacement) -> None:
        self._comparator = comparator
        self._placement = placement
        self._is_async = is_async_callable(comparator)

    def __call__(self, a: Any, b: Any) -> Any:
        # Dispatches on self._is_async unconditionally, exactly like
        # KeyComparator.__call__ - never on whether this particular pair
        # happens to involve None - so this callable is homogeneous per the
        # callable-dispatch contract: sort()'s one-time isawaitable trial
        # would otherwise see a plain int from a None-involving pair and
        # misclassify an async-wrapped comparator as sync.
        if self._is_async:
            return self._compare_async(a, b)
        return self._compare_sync(a, b)

    def _compare_sync(self, a: Any, b: Any) -> int:
        if a is None and b is None:
            return 0
        if a is None or b is None:
            return _null_sign(a is None, self._placement)
        return cast("int", self._comparator(a, b))

    async def _compare_async(self, a: Any, b: Any) -> int:
        if a is None and b is None:
            return 0
        if a is None or b is None:
            return _null_sign(a is None, self._placement)
        return await cast("Any", self._comparator)(a, b)


def _nulls_tolerant(comparator: "KeyComparator | Comparator[Any] | None", placement: NullPlacement) -> Any:
    if comparator is None:
        return KeyComparator(((_constant_key, False),), placement)
    if isinstance(comparator, KeyComparator):
        return KeyComparator(comparator.segments, placement)
    return _NullsComparator(comparator, placement)


@overload
def nulls_first(comparator: KeyComparator) -> KeyComparator: ...  # pragma: no cover


@overload
def nulls_first(comparator: None = None) -> KeyComparator: ...  # pragma: no cover


@overload
def nulls_first(comparator: "Comparator[T]") -> "Comparator[T]": ...  # pragma: no cover


def nulls_first(comparator: "KeyComparator | Comparator[Any] | None" = None) -> Any:
    """Build a Comparator that orders `None` before every non-`None` value,
    matching Java's `Comparator.nullsFirst`. `comparator` orders two non-`None`
    values; when omitted, every non-`None` value is equivalent to every other,
    as in Java's `nullsFirst(null)`.

    Also tolerates a null *key*, not only a null element: given a
    `KeyComparator` (what `comparing()` returns), the result is a
    `KeyComparator` whose segments are null-tolerant - so a `sorted()` built on
    it keeps the decorate-sort-undecorate fast path, and an element whose
    extracted key is `None` sorts as if the element itself were. Java reaches
    the key case only through the declined `comparing(f, nullsFirst(...))`
    overload; this closes it directly instead. Given any other `Comparator`,
    or none, the result is a plain wrapping comparator that checks for `None`
    and delegates otherwise.

    Composes like any other `Comparator`: `.then_comparing()` and
    `.reversed()` on a returned `KeyComparator` both keep the null tolerance
    (see `KeyComparator.then_comparing`/`reversed`).
    """
    return _nulls_tolerant(comparator, NullPlacement.FIRST)


@overload
def nulls_last(comparator: KeyComparator) -> KeyComparator: ...  # pragma: no cover


@overload
def nulls_last(comparator: None = None) -> KeyComparator: ...  # pragma: no cover


@overload
def nulls_last(comparator: "Comparator[T]") -> "Comparator[T]": ...  # pragma: no cover


def nulls_last(comparator: "KeyComparator | Comparator[Any] | None" = None) -> Any:
    """Build a Comparator that orders `None` after every non-`None` value,
    matching Java's `Comparator.nullsLast`. See `nulls_first`, whose rules -
    including the null-key tolerance Java has no direct route to - all apply
    here with `None` sorting to the opposite end.
    """
    return _nulls_tolerant(comparator, NullPlacement.LAST)
