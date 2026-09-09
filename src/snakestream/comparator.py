from enum import Enum, auto
from inspect import Parameter, signature
from typing import Any, cast, overload
from collections.abc import Callable

from snakestream.callable_dispatch import is_async_callable
from snakestream.exception import ComparatorContractException, StreamBuildException
from snakestream.type import Comparator, KeyExtractor, KeyExtractorComparator

# Named once so construction-time rejection (comparing()/then_comparing()) and
# the comparator-segment wrapper's raising path (sort.py, Decision 3) name the
# same two supported alternatives for the same reason.
ASYNC_COMPARATOR_MESSAGE = (
    "comparator must be synchronous; use an async key extractor segment instead "
    "(supported today), or pass an async comparator directly to sorted() "
    "(reaches _merge_sort())"
)


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
    both callers, so it carries their comparator-result type check rather than
    letting them add a second one. That check is written out, here as at every
    other site - delegating it measured ~5% - and routing these terminals
    through a Collector instead cost +26% (see this change's design.md).
    """
    if type(sign) is not int:
        raise ComparatorContractException(sign)
    return sign < 0 if asc else sign > 0


Segment = tuple[KeyExtractor, bool] | tuple[KeyExtractorComparator, bool]


def _reject_async_comparator(comparator: Comparator) -> None:
    """Construction-time half of `add-comparator-segments` Decision 2/3: an
    async supplied comparator
    has no key a sort tuple can hold, so it is refused here rather than
    falling back to a slower whole-chain path. The wrapper sort.py builds
    around a comparator segment's column (`_checked_segment_comparator`)
    catches the one shape this cannot - a plain `def __call__` that lies
    about being sync and returns a coroutine - with the same message."""
    if is_async_callable(comparator):
        raise StreamBuildException(ASYNC_COMPARATOR_MESSAGE)


_COMPARATOR_ARITY = 2


def _is_comparator_arity(fn: Callable) -> bool:
    """Decision 4: tell a bare `Comparator` from a key extractor by counting
    positional parameters. Only `*args` is genuinely ambiguous; it (and
    anything `inspect.signature` cannot introspect) resolves to False - key
    extractor, the meaning such a callable already carries today."""
    try:
        params = signature(fn).parameters.values()
    except TypeError, ValueError:
        return False
    count = 0
    for p in params:
        if p.kind is Parameter.VAR_POSITIONAL:
            return False
        if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
            count += 1
    return count == _COMPARATOR_ARITY


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


def _null_sign(a: Any, b: Any, placement: NullPlacement) -> int:
    """The sign a pair with at least one `None` side contributes, before any
    descending negation. Every case is decided here rather than split with the
    caller: a both-`None` pair is a tie and returns 0, and a one-sided pair
    sorts the `None` to whichever end `placement` names. The caller's only
    contract is that it does not call this when neither side is `None`."""
    if a is None and b is None:
        return 0
    if placement is NullPlacement.FIRST:
        return -1 if a is None else 1
    return -1 if b is None else 1


def _build_extract(extractor: KeyExtractor | None, nulls: NullPlacement, is_async: bool) -> Any:
    """The `(a, b) -> (ea, eb)` half of a segment, chosen once at construction.

    Every question this half used to re-ask per comparison - is there an
    extractor, does this segment await, does it pass `None` through - is a
    constant for the life of the comparator, so it is answered here and
    burned into a closure. The sync/async twinning survives only in the two
    keyed builders, which is the one place a segment can await.

    `NullPlacement.ABSENT` deliberately does **not** pass `None` through: it is
    the intolerant comparator every `comparing()` call builds, and calling the
    extractor on `None` - and raising out of it - is the behaviour it has always
    had. That is now structural: no tolerant builder is reachable when `nulls`
    is `ABSENT`.
    """
    if extractor is None:
        # A bare comparator segment compares the elements themselves, and can
        # never await - there is no extractor to be async.
        return lambda a, b: (a, b)
    f = extractor
    if nulls is NullPlacement.ABSENT:
        if is_async:

            async def extract_keyed_async(a: Any, b: Any) -> tuple[Any, Any]:
                return (await f(a), await f(b))

            return extract_keyed_async
        return lambda a, b: (f(a), f(b))
    if is_async:

        async def extract_tolerant_async(a: Any, b: Any) -> tuple[Any, Any]:
            return (a if a is None else await f(a), b if b is None else await f(b))

        return extract_tolerant_async
    return lambda a, b: (a if a is None else f(a), b if b is None else f(b))


def _build_compare_tolerant(comparator: Comparator | None, nulls: NullPlacement) -> Any:
    """The two null-tolerant leaves of `_build_compare`, split into their own
    builder so the enclosing function's branch count stays under ruff's C901
    ceiling - a shape question (design.md Risks), not a redesign. Both leaves
    check `ea is None or eb is None` before anything else, which is what makes
    a null *key* - not only a null element - sort by placement rather than
    reach natural ordering or a user comparator."""
    if comparator is None:

        def compare_tolerant_natural(ea: Any, eb: Any) -> int:
            if ea is None or eb is None:
                return _null_sign(ea, eb, nulls)
            return (ea > eb) - (ea < eb)

        return compare_tolerant_natural
    c = comparator

    def compare_tolerant_checked(ea: Any, eb: Any) -> int:
        if ea is None or eb is None:
            return _null_sign(ea, eb, nulls)
        sign = c(ea, eb)
        if type(sign) is not int:
            raise ComparatorContractException(sign)
        return sign

    return compare_tolerant_checked


def _build_compare(comparator: Comparator | None, nulls: NullPlacement) -> Any:
    """The `(ea, eb) -> sign` half of a segment, chosen once at construction.

    Always sync: a comparator is never awaited (`add-comparator-segments`
    Decision 2/3, enforced at construction by `_reject_async_comparator`), so
    this half is shared by the sync and async loops rather than written twice.
    That is what the closed roadmap item "Sharing the segment-sign tail costs
    one frame, ~10-19ns" (`roadmap/decisions.md`) was asking for - the shared
    tail costs no extra frame here, because it replaces the per-comparison
    `comparator is None` and `nulls is not ABSENT` tests rather than sitting
    behind them.

    `comparator is None` selects natural ordering and returns before the
    `type(sign) is not int` guard, since only a user-supplied comparator can
    fail it. It reads `ea`/`eb` rather than `a`/`b` on purpose: an extractor
    that *returns* `None` for a non-`None` element makes a null key, which a
    tolerant comparator places exactly as it places a null element. A
    both-`None` pair is a tie and folds into the ordinary `sign == 0` no-op the
    caller's loop already treats as "continue". The two tolerant leaves live in
    `_build_compare_tolerant`, one level down.
    """
    if nulls is not NullPlacement.ABSENT:
        return _build_compare_tolerant(comparator, nulls)
    if comparator is None:
        return lambda ea, eb: (ea > eb) - (ea < eb)
    c = comparator

    def compare_checked(ea: Any, eb: Any) -> int:
        sign = c(ea, eb)
        if type(sign) is not int:
            raise ComparatorContractException(sign)
        return sign

    return compare_checked


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
    or per comparison. `_plan` (`specialize-comparator-segments`, Decision 1)
    takes that one step further: a tuple of `(extract, compare, descending,
    is_async)` per segment, where `extract` and `compare` are themselves
    closures built by `_build_extract`/`_build_compare` - every question that
    is constant for the life of the comparator (is there an extractor, does
    this segment await, does it pass `None` through, is there a supplied
    comparator) answered once here rather than re-asked on every comparison.
    `.segments` remains untouched in shape - it is the tuple `sort.py`'s
    `_segment_column()` reads to choose its decorate-sort-undecorate fast
    path, and `_plan` is a derived view only `__call__` reads.

    `nulls` defaults to `NullPlacement.ABSENT`, so every `comparing(f)` call
    with no `nulls_first`/`nulls_last` in its history constructs exactly what
    it constructed before that factory pair existed.
    """

    def __init__(self, segments: tuple[Segment, ...], nulls: NullPlacement = NullPlacement.ABSENT) -> None:
        self.segments = segments
        self.nulls = nulls
        plan: list[tuple[Any, Any, bool, bool]] = []
        is_async: list[bool] = []
        for payload, descending in segments:
            if isinstance(payload, tuple):
                extractor, comparator = payload
            else:
                extractor, comparator = payload, None
            # A comparator segment's comparator is always sync (rejected
            # otherwise at construction) - only its optional extractor can
            # await, and a bare comparator segment (extractor None) never
            # does, which is what `extractor is not None` alone decides here.
            segment_is_async = extractor is not None and is_async_callable(extractor)
            plan.append(
                (
                    _build_extract(extractor, nulls, segment_is_async),
                    _build_compare(comparator, nulls),
                    descending,
                    segment_is_async,
                )
            )
            is_async.append(segment_is_async)
        self._plan = tuple(plan)
        self._any_async = any(is_async)

    def then_comparing(
        self, other: KeyExtractor | KeyComparator | Comparator, key_comparator: Comparator | None = None
    ) -> KeyComparator:
        """Append a tie-break ordering, matching Java's
        `Comparator.thenComparing`. `other` may be a bare key extractor,
        contributing one ascending segment; another `KeyComparator`, whose
        whole segment list - directions intact - is spliced in; or a bare
        `Comparator`, contributing a supplied ordering (add-comparator-segments,
        Decision 4 disambiguates the last two cases by arity). `key_comparator`,
        if given, orders the keys `other` extracts rather than their natural
        ordering (Decision 6). Returns a new `KeyComparator`; the receiver is
        unchanged.

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
        if key_comparator is not None:
            _reject_async_comparator(key_comparator)
            return KeyComparator((*self.segments, ((cast("KeyExtractor", other), key_comparator), False)), self.nulls)
        if _is_comparator_arity(other):
            comparator = cast("Comparator", other)
            _reject_async_comparator(comparator)
            return KeyComparator((*self.segments, ((None, comparator), False)), self.nulls)
        return KeyComparator((*self.segments, (cast("KeyExtractor", other), False)), self.nulls)

    def reversed(self) -> KeyComparator:
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
        flipped = cast("tuple[Segment, ...]", tuple((payload, not descending) for payload, descending in self.segments))
        return KeyComparator(flipped, self.nulls)

    def __call__(self, a: Any, b: Any) -> Any:
        if self._any_async:
            return self._compare_async(a, b)
        return self._compare_sync(a, b)

    def _compare_sync(self, a: Any, b: Any) -> int:
        # not self._any_async is what makes this branch reachable, so every
        # segment's extract half is a sync closure and none of them awaits.
        for extract, compare, descending, _is_async in self._plan:
            ea, eb = extract(a, b)
            sign = compare(ea, eb)
            if descending:
                sign = -sign
            if sign != 0:
                return sign
        return 0

    async def _compare_async(self, a: Any, b: Any) -> int:
        # A chain reaches here when *any* segment awaits; a sync segment inside
        # one still runs its sync closure directly rather than through a
        # coroutine that awaits nothing.
        for extract, compare, descending, is_async in self._plan:
            ea, eb = await extract(a, b) if is_async else extract(a, b)
            sign = compare(ea, eb)
            if descending:
                sign = -sign
            if sign != 0:
                return sign
        return 0


def comparing(key_extractor: KeyExtractor, key_comparator: Comparator | None = None) -> KeyComparator:
    """Build a Comparator that orders by an extracted key, matching Java's
    `Comparator.comparing(keyExtractor)`. `key_comparator`, if given, orders
    the extracted keys rather than their natural ordering, matching Java's
    two-argument `Comparator.comparing(keyExtractor, keyComparator)`
    (add-comparator-segments, Decision 6); it must be synchronous, though
    `key_extractor` may still be async.

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
    if key_comparator is not None:
        _reject_async_comparator(key_comparator)
        return KeyComparator((((key_extractor, key_comparator), False),))
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
        if a is None or b is None:
            return _null_sign(a, b, self._placement)
        return cast("int", self._comparator(a, b))

    async def _compare_async(self, a: Any, b: Any) -> int:
        if a is None or b is None:
            return _null_sign(a, b, self._placement)
        return await cast("Any", self._comparator)(a, b)


def _nulls_tolerant(comparator: KeyComparator | Comparator[Any] | None, placement: NullPlacement) -> Any:
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
def nulls_first[T](comparator: Comparator[T]) -> Comparator[T]: ...  # pragma: no cover


def nulls_first(comparator: KeyComparator | Comparator[Any] | None = None) -> Any:
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
def nulls_last[T](comparator: Comparator[T]) -> Comparator[T]: ...  # pragma: no cover


def nulls_last(comparator: KeyComparator | Comparator[Any] | None = None) -> Any:
    """Build a Comparator that orders `None` after every non-`None` value,
    matching Java's `Comparator.nullsLast`. See `nulls_first`, whose rules -
    including the null-key tolerance Java has no direct route to - all apply
    here with `None` sorting to the opposite end.
    """
    return _nulls_tolerant(comparator, NullPlacement.LAST)
