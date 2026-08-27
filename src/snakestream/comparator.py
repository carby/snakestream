from typing import Any, cast

from snakestream.callable_dispatch import is_async_callable
from snakestream.type import Comparator, KeyExtractor


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


class _KeyComparator:
    """The `Comparator` a `comparing()` call returns.

    Exposes `key_extractor` as a plain attribute so sort() can unwrap it and
    extract each key once, rather than the twice-per-comparison cost __call__
    below pays; __call__ exists so this is still a working Comparator for any
    consumer - min(), max(), min_by(), max_by() - that does not know to look
    for the attribute.
    """

    def __init__(self, key_extractor: KeyExtractor) -> None:
        self.key_extractor = key_extractor
        self._is_async = is_async_callable(key_extractor)

    def __call__(self, a: Any, b: Any) -> Any:
        if self._is_async:
            return self._compare_async(a, b)
        # not self._is_async is what makes this branch reachable, so the
        # extractor's sync arm is the one that ran - Any, not Awaitable[Any].
        ka = cast("Any", self.key_extractor(a))
        kb = cast("Any", self.key_extractor(b))
        return (ka > kb) - (ka < kb)

    async def _compare_async(self, a: Any, b: Any) -> int:
        ka = await self.key_extractor(a)
        kb = await self.key_extractor(b)
        return (ka > kb) - (ka < kb)


def comparing(key_extractor: KeyExtractor) -> Comparator:
    """Build a Comparator that orders by an extracted key, matching Java's
    `Comparator.comparing(keyExtractor)`.

    Returns an object rather than a plain `lambda a, b: ...` closure, because a
    closure would call key_extractor twice per comparison - O(n log n) times,
    which for an async key extractor is `2n log n` awaits. sort() recognizes
    this object (via its `key_extractor` attribute) and instead extracts each
    key exactly once and sorts on the keys directly, which is the whole reason
    this capability exists - see this change's proposal.md for the measured
    win. Every other comparator-consuming operation - min(), max(), min_by(),
    max_by() - still works via the ordinary __call__ path above, just without
    that fast path.

    key_extractor may be sync or async, like every other user-supplied
    callable in this library.

    There is no thenComparing() here to chain multiple keys - deliberately out
    of scope (see proposal.md). A tuple key gets the same effect in one pass:
    `comparing(lambda x: (x.last, x.first))`.
    """
    return _KeyComparator(key_extractor)
