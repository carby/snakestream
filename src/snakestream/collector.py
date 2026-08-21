# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from inspect import isawaitable
from typing import Any, Generic, NamedTuple, Protocol, TypeVar, cast, overload
from collections.abc import AsyncGenerator, Awaitable, Callable

from snakestream.execution import _maybe_aclosing
from snakestream.callable_dispatch import AsyncDispatch, _classify_step, _maybe_await, is_async_callable
from snakestream.exception import StreamBuildException
from snakestream.sink import Counter, TerminalSink, _UNSET
from snakestream.sort import is_new_extremum
from snakestream.type import (
    A,
    R,
    T,
    BiConsumer,
    BinaryOperator,
    Combiner,
    Comparator,
    Finisher,
    Mapper,
    NumberMapper,
    Predicate,
    Supplier,
)


class Collector(Generic[T, A, R]):
    """Java-style `Collector<T,A,R>`: `supplier()` creates a fresh
    accumulation container, `accumulator(container, element)` mutates it per
    element - its return value is ignored - and `finisher(container)`
    converts the finished container to the result (the container itself, if
    `finisher` is omitted). `combiner` is accepted for signature parity with
    Java and never invoked: a collection always folds over one composed
    stream, sequential or parallel, with no independently accumulated
    partitions to merge - the same posture `Stream.collect(supplier,
    accumulator, combiner)` and `reduce()`'s `combiner` already have.

    Every part may be sync or async. A `Collector` holds only these four
    callables, no per-collection state of its own, so one instance is safe to
    reuse across streams and across concurrent collections."""

    __slots__ = ("supplier", "accumulator", "combiner", "finisher")

    def __init__(
        self,
        supplier: Supplier[A],
        accumulator: BiConsumer[A, T],
        combiner: Combiner[A] | None = None,
        finisher: Finisher[A, R] | None = None,
    ) -> None:
        self.supplier = supplier
        self.accumulator = accumulator
        self.combiner = combiner
        self.finisher = finisher


class _CollectorSink(AsyncDispatch, TerminalSink[T]):
    """Adapts any Collector to the sink protocol: supplier -> container
    creation, accumulator -> accept(), finisher -> _finish(). The one
    AsyncDispatch triple here classifies the accumulator itself; a collector
    whose accumulator internally dispatches further user callables (a mapper,
    a comparator, ...) carries that classification state on its own
    supplier-made container instead, since this sink - like the Collector -
    is shared across collections."""

    def __init__(self, collector: Collector[Any, Any, Any]) -> None:
        super().__init__()
        self._collector = collector
        self._init_dispatch(collector.accumulator)

    def _create_container(self) -> Any:
        return self._collector.supplier()

    async def accept(self, element: Any) -> None:
        r = self._fn(self._container, element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r

    def _finish(self, container: Any) -> Any:
        finisher = self._collector.finisher
        return container if finisher is None else finisher(container)


class StreamingCollector:
    """The one collect() argument that is not a Collector: wraps a
    `(composition) -> AsyncGenerator` callable for a lazy, streaming result.
    Composed through the generator bridge rather than driven to a terminal
    sink, since a supplier/accumulator/finisher triple can only produce a
    value once the source is exhausted, and this one must not wait for
    that."""

    __slots__ = ("_fn",)

    def __init__(self, fn: Callable[[AsyncGenerator[Any, None]], AsyncGenerator[Any, None]]) -> None:
        self._fn = fn

    def __call__(self, composition: AsyncGenerator[Any, None]) -> AsyncGenerator[Any, None]:
        return self._fn(composition)


async def _stream(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    # _maybe_aclosing, not aclosing: to_generator() also accepts a plain
    # AsyncIterable with no aclose() (a custom __anext__-only iterator)
    async with _maybe_aclosing(composition) as src:
        async for n in src:
            yield n


to_generator = StreamingCollector(_stream)


# A factory, like every other collector here and like Java's
# Collectors.toList(). A Collector holds no per-collection state, so the
# instance one call returns is still safe to reuse across collections - the
# factory shape is about one consistent rule for the public surface, not
# about state.
def to_list() -> Collector[T, list[T], list[T]]:
    return Collector(list, list.append)


def to_set() -> Collector[T, set[T], set[T]]:
    return Collector(set, set.add)


def joining(delimiter: str = "", prefix: str = "", suffix: str = "") -> Collector[str, list[str], str]:
    def _finish(parts: list[str]) -> str:
        return prefix + delimiter.join(parts) + suffix

    return Collector(list, list.append, finisher=_finish)


def counting() -> Collector[Any, Any, int]:
    def _accumulate(container: Counter, element: Any) -> None:
        container.value += 1

    def _finish(container: Counter) -> int:
        return container.value

    return Collector(Counter, _accumulate, finisher=_finish)


# summing_int/summing_long and averaging_int/averaging_long/averaging_double
# are intentionally kept as separate public names: Java's Collectors
# distinguishes them by primitive type (int/long/double), a distinction
# Python's numeric tower doesn't have. The names mirror the distinct Java
# methods; the bodies behind them are shared, since only summing_double's
# seed and coercion actually differ.


class _SumBox:
    __slots__ = ("total", "is_async", "checked")

    def __init__(self, seed: int | float) -> None:
        self.total = seed
        self.is_async = False
        self.checked = False


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


class _AvgBox:
    __slots__ = ("total", "count", "is_async", "checked")

    def __init__(self) -> None:
        self.total = 0.0
        self.count = 0
        self.is_async = False
        self.checked = False


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


class _SummaryBox:
    __slots__ = ("count", "total", "least", "greatest", "is_async", "checked")

    def __init__(self, seed: int | float) -> None:
        self.count = 0
        self.total = seed
        self.least: int | float | None = None
        self.greatest: int | float | None = None
        self.is_async = False
        self.checked = False


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


class _ExtremumBox:
    __slots__ = ("found", "is_async", "checked")

    def __init__(self) -> None:
        self.found: Any = _UNSET
        self.is_async = False
        self.checked = False


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


class _ReduceBox:
    __slots__ = ("acc", "mapper_is_async", "mapper_checked", "op_is_async", "op_checked")

    def __init__(self, identity: Any) -> None:
        self.acc = identity
        self.mapper_is_async = False
        self.mapper_checked = False
        self.op_is_async = False
        self.op_checked = False


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


class _ToMapBox:
    __slots__ = (
        "result",
        "key_is_async",
        "key_checked",
        "value_is_async",
        "value_checked",
        "merge_is_async",
        "merge_checked",
    )

    def __init__(self) -> None:
        self.result: dict[Any, Any] = {}
        self.key_is_async = False
        self.key_checked = False
        self.value_is_async = False
        self.value_checked = False
        self.merge_is_async = False
        self.merge_checked = False


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
                raise ValueError(f"Duplicate key: {key!r}")
            merged, container.merge_is_async, container.merge_checked = _classify_step(
                merge_function, container.merge_is_async, container.merge_checked, container.result[key], value
            )
            value = await merged if container.merge_is_async else merged
        container.result[key] = value

    def _finish(container: _ToMapBox) -> dict[R, Any]:
        return container.result

    return Collector(_supply, _accumulate, finisher=_finish)


class _GroupBox:
    __slots__ = ("groups", "key_is_async", "key_checked", "acc_is_async", "acc_checked")

    def __init__(self, initial: dict[Any, Any]) -> None:
        self.groups = initial
        self.key_is_async = False
        self.key_checked = False
        self.acc_is_async = False
        self.acc_checked = False


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
    result = {}
    for key, sub in groups.items():
        result[key] = await _maybe_await(finisher, sub) if finisher is not None else sub
    return result


def _check_downstream(downstream: Collector[Any, Any, Any]) -> None:
    if not isinstance(downstream, Collector):
        raise StreamBuildException("downstream must be a Collector")


def grouping_by(
    classifier: Mapper[T, R],
    downstream: Collector[T, Any, Any] = to_list(),
) -> Collector[T, Any, dict[R, Any]]:
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
    downstream: Collector[T, Any, Any] = to_list(),
) -> Collector[T, Any, dict[bool, Any]]:
    _check_downstream(downstream)

    async def _supply() -> _GroupBox:
        groups: dict[Any, Any] = {}
        for key in (True, False):
            groups[key] = await _maybe_await(downstream.supplier)
        return _GroupBox(groups)

    async def _accumulate(container: _GroupBox, element: T) -> None:
        # bool() as coerce_key, not as a wrapper round the predicate: a truthy
        # non-bool predicate result must land in the True bucket, as today.
        await _group_into(container, predicate, downstream, element, bool)

    def _finish(container: _GroupBox) -> Any:
        return _finish_groups(downstream, container.groups)

    return Collector(_supply, _accumulate, finisher=_finish)


class _MappingBox:
    __slots__ = ("container", "mapper_is_async", "mapper_checked", "acc_is_async", "acc_checked")

    def __init__(self, container: Any) -> None:
        self.container = container
        self.mapper_is_async = False
        self.mapper_checked = False
        self.acc_is_async = False
        self.acc_checked = False


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

    return Collector(_supply, _accumulate, finisher=_finish)


class _CollectAndThenBox:
    __slots__ = ("container", "acc_is_async", "acc_checked")

    def __init__(self, container: Any) -> None:
        self.container = container
        self.acc_is_async = False
        self.acc_checked = False


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

    return Collector(_supply, _accumulate, finisher=_finish)


class _SupportsAdd(Protocol):
    def add(self, item: Any) -> Any: ...


_C = TypeVar("_C", bound=_SupportsAdd)


def to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C, _C]:
    async def _supply() -> _C:
        return await _maybe_await(collection_supplier)

    def _accumulate(container: _C, element: Any) -> None:
        container.add(element)

    return Collector(_supply, _accumulate)
