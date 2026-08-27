"""The collector factories: to_list(), grouping_by(), summing_int() and the
rest, each returning a Collector. Java names this pair too - Collector is the
interface, Collectors the class that holds the factories - and the import
edge runs one way, collectors -> collector, never back."""

from __future__ import annotations

from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, NamedTuple, cast, overload
from collections.abc import Awaitable, Callable

from snakestream.callable_dispatch import _classify_step, _maybe_await, is_async_callable
from snakestream.collector import Characteristics, Collector
from snakestream.comparator import is_new_extremum
from snakestream.exception import IllegalStateException, StreamBuildException
from snakestream.sink import Box, _UNSET
from snakestream.type import (
    R,
    T,
    BinaryOperator,
    Comparator,
    Finisher,
    Mapper,
    NumberMapper,
    Predicate,
    Supplier,
    _C,
)


# Every name in this module is a factory, like Java's Collectors.toList().
# A Collector holds no per-collection state, so the instance one call returns
# is still safe to reuse across collections - the factory shape is about one
# consistent rule for the public surface, not about state.
def to_list() -> Collector[T, list[T], list[T]]:
    return Collector(list, list.append)


# The default downstream for grouping_by()/partitioning_by(), named here rather
# than called in their signatures. A Collector is four callables and no
# per-collection state -- every group's list comes from the supplier, not from
# the Collector -- so one shared value is safe, and saying so at the default
# site spares the reader a trip to Collector's docstring to rule out the
# mutable-default bug (B008).
_TO_LIST: Collector[Any, list[Any], list[Any]] = to_list()


def to_set() -> Collector[T, set[T], set[T]]:
    # The only factory in this module whose Java counterpart carries
    # UNORDERED (CH_UNORDERED_ID). The declaration is true of the behaviour,
    # not merely asserted: a set retains no record of insertion order.
    return Collector(set, set.add, characteristics=(Characteristics.UNORDERED,))


def joining(delimiter: str = "", prefix: str = "", suffix: str = "") -> Collector[str, list[str], str]:
    def _finish(parts: list[str]) -> str:
        return prefix + delimiter.join(parts) + suffix

    return Collector(list, list.append, finisher=_finish)


def counting() -> Collector[Any, Any, int]:
    # Order-blind in fact - counting the same elements in any order gives the
    # same count - but left undeclared, matching Java: OpenJDK gives counting()
    # and the rest below (summing_*, averaging_*, summarizing_*, to_map,
    # grouping_by, partitioning_by) CH_ID/CH_NOID rather than CH_UNORDERED_ID,
    # because Java's UNORDERED governs its combine strategy, where an
    # associative reduction is safe either way and the mark buys nothing.
    # Under the roadmap's item 1 the mark would buy skipping the reorder
    # barrier here - a real divergence from Java, and item 1's to weigh with a
    # benchmark, not this change's to decide by inspection. min_by/max_by are
    # excluded from that reconsideration regardless: is_new_extremum() keeps
    # the earlier element on a tie, so which of two equal elements is returned
    # is an encounter-order question, not an order-blind one.
    def _accumulate(container: Box, element: Any) -> None:
        container.value += 1

    def _finish(container: Box) -> int:
        return container.value

    return Collector(lambda: Box(0), _accumulate, finisher=_finish)


# summing_int/summing_long and averaging_int/averaging_long/averaging_double
# are intentionally kept as separate public names: Java's Collectors
# distinguishes them by primitive type (int/long/double), a distinction
# Python's numeric tower doesn't have. The names mirror the distinct Java
# methods; the bodies behind them are shared, since only summing_double's
# seed and coercion actually differ.


@dataclass(slots=True)
class _SumBox:
    total: int | float
    is_async: bool = False
    checked: bool = False


def _summing(mapper: NumberMapper, seed: int | float, coerce: Callable[[Any], Any] | None) -> Collector[Any, _SumBox, Any]:
    # coerce is None means "add the mapped value as-is", not "coerce with an
    # identity function": the int/long path must preserve whatever numeric type
    # the mapper returns (a Decimal, a Fraction), and an identity call there
    # would sit on the per-element path.
    def _supply() -> _SumBox:
        box = _SumBox(seed)
        box.is_async = is_async_callable(mapper)
        return box

    async def _accumulate(container: _SumBox, element: Any) -> None:
        r = mapper(element)
        if container.is_async:
            r = await cast("Awaitable[int | float]", r)
        elif not container.checked:
            container.checked = True
            if isawaitable(r):
                container.is_async = True
                r = await r
        container.total += cast(Any, r) if coerce is None else coerce(cast(Any, r))

    def _finish(container: _SumBox) -> Any:
        return container.total

    return Collector(_supply, _accumulate, finisher=_finish)


@dataclass(slots=True)
class _AvgBox:
    total: float = 0.0
    count: int = 0
    is_async: bool = False
    checked: bool = False


def _averaging(mapper: NumberMapper) -> Collector[Any, _AvgBox, float]:
    def _supply() -> _AvgBox:
        box = _AvgBox()
        box.is_async = is_async_callable(mapper)
        return box

    async def _accumulate(container: _AvgBox, element: Any) -> None:
        r = mapper(element)
        if container.is_async:
            r = await cast("Awaitable[int | float]", r)
        elif not container.checked:
            container.checked = True
            if isawaitable(r):
                container.is_async = True
                r = await r
        container.total += cast(Any, r)
        container.count += 1

    def _finish(container: _AvgBox) -> float:
        return container.total / container.count if container.count else 0.0

    return Collector(_supply, _accumulate, finisher=_finish)


def summing_int(mapper: NumberMapper) -> Collector[Any, Any, int]:
    return _summing(mapper, 0, None)


def summing_long(mapper: NumberMapper) -> Collector[Any, Any, int]:
    return _summing(mapper, 0, None)


def summing_double(mapper: NumberMapper) -> Collector[Any, Any, float]:
    return _summing(mapper, 0.0, float)


def averaging_int(mapper: NumberMapper) -> Collector[Any, Any, float]:
    return _averaging(mapper)


def averaging_long(mapper: NumberMapper) -> Collector[Any, Any, float]:
    return _averaging(mapper)


def averaging_double(mapper: NumberMapper) -> Collector[Any, Any, float]:
    return _averaging(mapper)


class SummaryStatistics(NamedTuple):
    count: int
    sum: int | float
    min: int | float | None
    max: int | float | None
    average: float


@dataclass(slots=True)
class _SummaryBox:
    total: int | float
    count: int = 0
    least: int | float | None = None
    greatest: int | float | None = None
    is_async: bool = False
    checked: bool = False


def _summarizing(
    mapper: NumberMapper, seed: int | float, coerce: Callable[[Any], Any] | None
) -> Collector[Any, _SummaryBox, SummaryStatistics]:
    def _supply() -> _SummaryBox:
        box = _SummaryBox(seed)
        box.is_async = is_async_callable(mapper)
        return box

    async def _accumulate(container: _SummaryBox, element: Any) -> None:
        r = mapper(element)
        if container.is_async:
            r = await cast("Awaitable[int | float]", r)
        elif not container.checked:
            container.checked = True
            if isawaitable(r):
                container.is_async = True
                r = await r
        value = cast(Any, r) if coerce is None else coerce(cast(Any, r))
        container.count += 1
        container.total += value
        if container.least is None or value < container.least:
            container.least = value
        if container.greatest is None or value > container.greatest:
            container.greatest = value

    def _finish(container: _SummaryBox) -> SummaryStatistics:
        average = container.total / container.count if container.count else 0.0
        return SummaryStatistics(container.count, container.total, container.least, container.greatest, average)

    return Collector(_supply, _accumulate, finisher=_finish)


def summarizing_int(mapper: NumberMapper) -> Collector[Any, Any, SummaryStatistics]:
    return _summarizing(mapper, 0, None)


def summarizing_long(mapper: NumberMapper) -> Collector[Any, Any, SummaryStatistics]:
    return _summarizing(mapper, 0, None)


def summarizing_double(mapper: NumberMapper) -> Collector[Any, Any, SummaryStatistics]:
    return _summarizing(mapper, 0.0, float)


@dataclass(slots=True)
class _ExtremumBox:
    found: Any = _UNSET
    is_async: bool = False
    checked: bool = False


def _extremum(comparator: Comparator[T], asc: bool) -> Collector[T, _ExtremumBox, T | None]:
    def _supply() -> _ExtremumBox:
        box = _ExtremumBox()
        box.is_async = is_async_callable(comparator)
        return box

    async def _accumulate(container: _ExtremumBox, element: T) -> None:
        if container.found is _UNSET:
            container.found = element
            return

        sign = comparator(element, container.found)
        if container.is_async:
            sign = await cast("Awaitable[int]", sign)
        elif not container.checked:
            container.checked = True
            if isawaitable(sign):
                container.is_async = True
                sign = await sign
        if is_new_extremum(cast(int, sign), asc):
            container.found = element

    def _finish(container: _ExtremumBox) -> T | None:
        return None if container.found is _UNSET else container.found

    return Collector(_supply, _accumulate, finisher=_finish)


def min_by(comparator: Comparator[T]) -> Collector[T, Any, T | None]:
    return _extremum(comparator, asc=True)


def max_by(comparator: Comparator[T]) -> Collector[T, Any, T | None]:
    return _extremum(comparator, asc=False)


@dataclass(slots=True)
class _ReduceBox:
    acc: Any
    mapper_is_async: bool = False
    mapper_checked: bool = False
    op_is_async: bool = False
    op_checked: bool = False


@overload
def reducing(binary_operator: BinaryOperator[T]) -> Collector[T, Any, T | None]: ...  # pragma: no cover


@overload
def reducing(identity: T, binary_operator: BinaryOperator[T]) -> Collector[T, Any, T]: ...  # pragma: no cover


@overload
def reducing(
    identity: R, mapper: Mapper[T, R], binary_operator: BinaryOperator[R]
) -> Collector[T, Any, R]: ...  # pragma: no cover


def reducing(identity: Any = _UNSET, mapper: Any = _UNSET, binary_operator: Any = _UNSET) -> Any:
    """Implements the same _UNSET-seed fold as terminals.py's _ReduceSink, and
    the same empty-finishes-as-None rule. The duplication is deliberate and
    measured - see that sink's docstring - so a change to either rule belongs
    in both places."""
    if mapper is _UNSET:
        # Called as reducing(binary_operator): the single positional arg is
        # the fold operator, with no identity and no element mapper.
        identity, mapper, binary_operator = _UNSET, None, identity
    elif binary_operator is _UNSET:
        # Called as reducing(identity, binary_operator): the second
        # positional arg is the fold operator, with no element mapper.
        mapper, binary_operator = None, mapper

    def _supply() -> _ReduceBox:
        return _ReduceBox(identity)

    async def _accumulate(container: _ReduceBox, element: Any) -> None:
        if mapper is not None:
            value, container.mapper_is_async, container.mapper_checked = _classify_step(
                mapper, container.mapper_is_async, container.mapper_checked, element
            )
            if container.mapper_is_async:
                value = await value
        else:
            value = element
        if container.acc is _UNSET:
            container.acc = value
            return
        r, container.op_is_async, container.op_checked = _classify_step(
            binary_operator, container.op_is_async, container.op_checked, container.acc, value
        )
        if container.op_is_async:
            r = await r
        container.acc = r

    def _finish(container: _ReduceBox) -> Any:
        return None if container.acc is _UNSET else container.acc

    return Collector(_supply, _accumulate, finisher=_finish)


@dataclass(slots=True)
class _ToMapBox:
    result: dict[Any, Any] = field(default_factory=dict)
    key_is_async: bool = False
    key_checked: bool = False
    value_is_async: bool = False
    value_checked: bool = False
    merge_is_async: bool = False
    merge_checked: bool = False


def to_map(
    key_mapper: Mapper[T, R],
    value_mapper: Mapper[T, Any],
    merge_function: BinaryOperator[Any] | None = None,
) -> Collector[T, Any, dict[R, Any]]:
    def _supply() -> _ToMapBox:
        return _ToMapBox()

    async def _accumulate(container: _ToMapBox, element: T) -> None:
        key, container.key_is_async, container.key_checked = _classify_step(
            key_mapper, container.key_is_async, container.key_checked, element
        )
        if container.key_is_async:
            key = await key
        value, container.value_is_async, container.value_checked = _classify_step(
            value_mapper, container.value_is_async, container.value_checked, element
        )
        if container.value_is_async:
            value = await value
        if key in container.result:
            if merge_function is None:
                raise IllegalStateException(f"Duplicate key: {key!r}")
            merged, container.merge_is_async, container.merge_checked = _classify_step(
                merge_function, container.merge_is_async, container.merge_checked, container.result[key], value
            )
            value = await merged if container.merge_is_async else merged
        container.result[key] = value

    def _finish(container: _ToMapBox) -> dict[R, Any]:
        return container.result

    return Collector(_supply, _accumulate, finisher=_finish)


@dataclass(slots=True)
class _GroupBox:
    groups: dict[Any, Any]
    key_is_async: bool = False
    key_checked: bool = False
    acc_is_async: bool = False
    acc_checked: bool = False


async def _group_into(
    container: _GroupBox,
    key_fn: Callable[[Any], Any],
    downstream: Collector[Any, Any, Any],
    element: Any,
    coerce_key: Callable[[Any], Any] | None = None,
) -> None:
    # The shared step behind grouping_by/partitioning_by: classify the
    # element's key, materialise that key's downstream container on first
    # sight, and accumulate the element into it. The two differ only in the
    # key_fn they pass, in whether groups is pre-seeded, and in coerce_key.
    #
    # coerce_key runs on the *awaited* key, which is why partitioning_by's
    # bool() cannot simply wrap its predicate: dispatch classifies and awaits
    # key_fn's result, so a sync bool()-wrapper would see an unawaited
    # coroutine for an async predicate and call every element True.
    key, container.key_is_async, container.key_checked = _classify_step(
        key_fn, container.key_is_async, container.key_checked, element
    )
    if container.key_is_async:
        key = await key
    if coerce_key is not None:
        key = coerce_key(key)
    if key not in container.groups:
        container.groups[key] = await _maybe_await(downstream.supplier)
    r, container.acc_is_async, container.acc_checked = _classify_step(
        downstream.accumulator, container.acc_is_async, container.acc_checked, container.groups[key], element
    )
    if container.acc_is_async:
        await r


async def _finish_groups(downstream: Collector[Any, Any, Any], groups: dict[Any, Any]) -> dict[Any, Any]:
    finisher = downstream.finisher
    # the finisher is fixed for the whole collection, so the test belongs
    # outside the loop rather than once per group.
    if finisher is None:
        return dict(groups)
    return {key: await _maybe_await(finisher, sub) for key, sub in groups.items()}


def _check_downstream(downstream: Collector[Any, Any, Any]) -> None:
    if not isinstance(downstream, Collector):
        raise StreamBuildException("downstream must be a Collector")


def grouping_by(
    classifier: Mapper[T, R],
    downstream: Collector[T, Any, Any] = _TO_LIST,
) -> Collector[T, Any, dict[R, Any]]:
    # Takes a downstream but deliberately does not derive characteristics from
    # it, unlike mapping()/collecting_and_then(): the downstream's result is a
    # map *value*, and a trait of the values says nothing about the map itself.
    # grouping_by(f, to_set()) builds a dict whose insertion order follows
    # encounter order, so deriving UNORDERED from the inner to_set() would be
    # wrong, not merely conservative.
    _check_downstream(downstream)

    def _supply() -> _GroupBox:
        return _GroupBox({})

    async def _accumulate(container: _GroupBox, element: T) -> None:
        await _group_into(container, classifier, downstream, element)

    def _finish(container: _GroupBox) -> Any:
        return _finish_groups(downstream, container.groups)

    return Collector(_supply, _accumulate, finisher=_finish)


def partitioning_by(
    predicate: Predicate[T],
    downstream: Collector[T, Any, Any] = _TO_LIST,
) -> Collector[T, Any, dict[bool, Any]]:
    # Same reasoning as grouping_by() above: takes a downstream, deliberately
    # does not derive characteristics from it, because the downstream's
    # result is a map value and says nothing about the (always two-key) map.
    _check_downstream(downstream)

    async def _supply() -> _GroupBox:
        # both buckets exist before any element arrives, so partitioning_by
        # always yields a two-key dict even over an empty stream.
        return _GroupBox({True: await _maybe_await(downstream.supplier), False: await _maybe_await(downstream.supplier)})

    async def _accumulate(container: _GroupBox, element: T) -> None:
        # bool() as coerce_key, not as a wrapper round the predicate: a truthy
        # non-bool predicate result must land in the True bucket, as today.
        await _group_into(container, predicate, downstream, element, bool)

    def _finish(container: _GroupBox) -> Any:
        return _finish_groups(downstream, container.groups)

    return Collector(_supply, _accumulate, finisher=_finish)


@dataclass(slots=True)
class _MappingBox:
    container: Any
    mapper_is_async: bool = False
    mapper_checked: bool = False
    acc_is_async: bool = False
    acc_checked: bool = False


def mapping(mapper: Mapper[T, R], downstream: Collector[R, Any, Any]) -> Collector[T, Any, Any]:
    _check_downstream(downstream)

    async def _supply() -> _MappingBox:
        return _MappingBox(await _maybe_await(downstream.supplier))

    async def _accumulate(container: _MappingBox, element: T) -> None:
        value, container.mapper_is_async, container.mapper_checked = _classify_step(
            mapper, container.mapper_is_async, container.mapper_checked, element
        )
        if container.mapper_is_async:
            value = await value
        r, container.acc_is_async, container.acc_checked = _classify_step(
            downstream.accumulator, container.acc_is_async, container.acc_checked, container.container, value
        )
        if container.acc_is_async:
            await r

    def _finish(container: _MappingBox) -> Any:
        finisher = downstream.finisher
        return container.container if finisher is None else finisher(container.container)

    # The mapper runs per element and the result is downstream's unchanged, so
    # every trait of that result - including UNORDERED - is downstream's too.
    return Collector(_supply, _accumulate, finisher=_finish, characteristics=downstream.characteristics)


@dataclass(slots=True)
class _CollectAndThenBox:
    container: Any
    acc_is_async: bool = False
    acc_checked: bool = False


async def _finish_collecting_and_then(
    downstream: Collector[Any, Any, Any], finisher: Finisher[Any, Any], container: Any
) -> Any:
    downstream_finisher = downstream.finisher
    result = await _maybe_await(downstream_finisher, container) if downstream_finisher is not None else container
    return await _maybe_await(finisher, result)


def collecting_and_then(downstream: Collector[T, Any, R], finisher: Finisher[R, Any]) -> Collector[T, Any, Any]:
    _check_downstream(downstream)

    async def _supply() -> _CollectAndThenBox:
        return _CollectAndThenBox(await _maybe_await(downstream.supplier))

    async def _accumulate(container: _CollectAndThenBox, element: T) -> None:
        r, container.acc_is_async, container.acc_checked = _classify_step(
            downstream.accumulator, container.acc_is_async, container.acc_checked, container.container, element
        )
        if container.acc_is_async:
            await r

    def _finish(container: _CollectAndThenBox) -> Any:
        return _finish_collecting_and_then(downstream, finisher, container.container)

    # finisher runs once on the finished result, not per element, so it
    # cannot introduce a dependence on arrival order - downstream's
    # characteristics carry over unchanged. Java additionally clears
    # IDENTITY_FINISH here, since adding a finisher is what makes the finish
    # non-identity; not done here because that member does not exist yet -
    # whoever adds it adds the clearing with it.
    return Collector(_supply, _accumulate, finisher=_finish, characteristics=downstream.characteristics)


def to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C, _C]:
    async def _supply() -> _C:
        return await _maybe_await(collection_supplier)

    def _accumulate(container: _C, element: Any) -> None:
        container.add(element)

    return Collector(_supply, _accumulate)
