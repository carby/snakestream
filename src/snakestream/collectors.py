"""The collector factories: to_list(), grouping_by(), summing_int() and the
rest, each returning a Collector. Java names this pair too - Collector is the
interface, Collectors the class that holds the factories - and the import
edge runs one way, collectors -> collector, never back."""

from __future__ import annotations

from dataclasses import dataclass
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
    _M,
)


# The mark the order-blind factories below declare. Named once so the reason
# lives in one place: UNORDERED here means "any two orderings of the same
# elements collect to a result that compares equal", which is a claim about the
# collected value and nothing else. Java's javadoc documents characteristics for
# toSet(), groupingByConcurrent() and toConcurrentMap() only, so declaring it
# elsewhere diverges from no documented contract; OpenJDK's private CH_ID on
# these factories reflects that Java's UNORDERED governs its *combine* strategy,
# where an associative reduction is safe either way and the mark buys nothing.
# Here it governs the racing delivery barrier instead, which is why the same
# declaration is worth making (roadmap question 4, closed 2026-08-31 on a
# tail-latency benchmark: the barrier costs 1.12-1.27x on IO work whose
# latencies are skewed, where a uniform-latency benchmark had shown nothing).
_ORDER_BLIND = (Characteristics.UNORDERED,)


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
    # not merely asserted: two sets holding the same members compare equal
    # irrespective of the order either was built in, which is what UNORDERED
    # promises. It promises nothing about iteration order, and a set's does
    # depend on insertion history.
    return Collector(set, set.add, characteristics=(Characteristics.UNORDERED,))


def joining(delimiter: str = "", prefix: str = "", suffix: str = "") -> Collector[str, list[str], str]:
    def _finish(parts: list[str]) -> str:
        return prefix + delimiter.join(parts) + suffix

    return Collector(list, list.append, finisher=_finish)


def counting() -> Collector[Any, Any, int]:
    # Declares UNORDERED (see _ORDER_BLIND): counting the same elements in any
    # order gives the same int, so the declaration is true of the behaviour and
    # not merely asserted. min_by/max_by are excluded for good - collector-min-max
    # requires them not to declare it, because they return an *element* and so
    # have a tie to break, which counting does not.
    def _accumulate(container: Box, element: Any) -> None:
        container.value += 1

    def _finish(container: Box) -> int:
        return container.value

    return Collector(lambda: Box(0), _accumulate, finisher=_finish, characteristics=_ORDER_BLIND)


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


def _summing(
    mapper: NumberMapper,
    seed: int | float,
    coerce: Callable[[Any], Any] | None,
    characteristics: tuple[Characteristics, ...] = (),
) -> Collector[Any, _SumBox, Any]:
    # coerce is None means "add the mapped value as-is", not "coerce with an
    # identity function": the int/long path must preserve whatever numeric type
    # the mapper returns (a Decimal, a Fraction), and an identity call there
    # would sit on the per-element path.
    #
    # characteristics is a parameter rather than something derived from coerce
    # because the two answer different questions that happen to agree today.
    # Each caller states its own mark, so summing_double() cannot inherit
    # summing_int()'s by sharing this body.
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

    return Collector(_supply, _accumulate, finisher=_finish, characteristics=characteristics)


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


# summing_int/summing_long declare UNORDERED: integer addition is exact and
# associative, so summing the same mapped values in any order gives the same int.
def summing_int(mapper: NumberMapper) -> Collector[Any, Any, int]:
    return _summing(mapper, 0, None, _ORDER_BLIND)


def summing_long(mapper: NumberMapper) -> Collector[Any, Any, int]:
    return _summing(mapper, 0, None, _ORDER_BLIND)


# summing_double and the averaging_* family below are permanently unmarkable,
# not merely undeclared: float addition is not associative, so two orderings of
# the same elements can sum to values that differ in the last place and compare
# unequal. They are order-*sensitive in fact*, which is a firmer exclusion than
# Java's silence - a later pass revisiting the marking question should treat
# them as closed rather than re-weigh them. averaging_int/averaging_long are
# included despite their int inputs, because each divides a float accumulator.
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
    mapper: NumberMapper,
    seed: int | float,
    coerce: Callable[[Any], Any] | None,
    characteristics: tuple[Characteristics, ...] = (),
) -> Collector[Any, _SummaryBox, SummaryStatistics]:
    # characteristics is stated per caller, as in _summing(): sharing this body
    # must not let summarizing_double() inherit summarizing_int()'s mark.
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

    return Collector(_supply, _accumulate, finisher=_finish, characteristics=characteristics)


# summarizing_int/summarizing_long declare UNORDERED, and the claim is only as
# strong as the weakest field: SummaryStatistics is a NamedTuple, so == compares
# every one of count, sum, min, max and average. Over int inputs each is exact -
# count and sum are associative, min and max select a *value* rather than an
# element (so unlike min_by/max_by there is no tie identity to preserve), and
# average is that exact sum over that exact count.
def summarizing_int(mapper: NumberMapper) -> Collector[Any, Any, SummaryStatistics]:
    return _summarizing(mapper, 0, None, _ORDER_BLIND)


def summarizing_long(mapper: NumberMapper) -> Collector[Any, Any, SummaryStatistics]:
    return _summarizing(mapper, 0, None, _ORDER_BLIND)


# Permanently unmarkable for the same reason as summing_double, and the
# NamedTuple makes it sharper: sum accumulates in float, so one order-sensitive
# field is enough to make the whole result compare unequal, however exact the
# count/min/max fields beside it are.
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
    result: Any
    key_is_async: bool = False
    key_checked: bool = False
    value_is_async: bool = False
    value_checked: bool = False
    merge_is_async: bool = False
    merge_checked: bool = False


@overload
def to_map(key_mapper: Mapper[T, R], value_mapper: Mapper[T, Any]) -> Collector[T, Any, dict[R, Any]]: ...  # pragma: no cover


@overload
def to_map(
    key_mapper: Mapper[T, R], value_mapper: Mapper[T, Any], merge_function: BinaryOperator[Any]
) -> Collector[T, Any, dict[R, Any]]: ...  # pragma: no cover


@overload
def to_map(
    key_mapper: Mapper[T, R],
    value_mapper: Mapper[T, Any],
    merge_function: BinaryOperator[Any],
    map_supplier: Supplier[_M],
) -> Collector[T, Any, _M]: ...  # pragma: no cover


# The overload block is exactly Java's three toMap overloads, and what it
# *excludes* is the point: there is no to_map(k, v, map_supplier) form, because
# Java has none. Adding one would expand the public surface rather than close a
# parity gap, and it is what keeps the container out of the characteristics
# decision below - the 4-arg form always carries a merge_function, so it
# declares nothing on the merge's account alone.
#
# The exclusion is enforced by the declared surface and `ty`, not by a runtime
# raise: telling "a merge function" from "a mapping type" would need to inspect
# a callable, and both are callables of the right shape. There is no honest
# predicate for it.
def to_map(
    key_mapper: Mapper[T, R],
    value_mapper: Mapper[T, Any],
    merge_function: BinaryOperator[Any] | None = None,
    map_supplier: Supplier[Any] = dict,
) -> Collector[T, Any, Any]:
    # async unconditionally rather than branching on whether map_supplier was
    # given: a supplier runs once per *collection*, not per element, so the
    # module's usual reason to keep a sync fast path does not apply here, and
    # one code path is worth more than one coroutine per collect.
    async def _supply() -> _ToMapBox:
        return _ToMapBox(await _maybe_await(map_supplier))

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

    def _finish(container: _ToMapBox) -> Any:
        # the caller's own mapping, returned as-is rather than copied into a
        # dict, so a supplied type reaches the caller intact.
        return container.result

    # The one factory here whose characteristics come from its arguments rather
    # than from its identity or from a downstream's. The two forms differ in
    # exactly what UNORDERED asserts (see _ORDER_BLIND for what that is):
    #
    # With no merge_function the collected dict is a function of the element
    # multiset alone - each key and value comes from one element and consults no
    # other, dict equality ignores key order, and any multiset that would make
    # the result depend on order raises instead. So it declares.
    #
    # With one it cannot, and never will: merge_function is caller-supplied and
    # need not commute. `lambda a, b: a` keeps whichever value arrived first,
    # which is a different dict under a different order. This exclusion is
    # permanent rather than merely undeclared, the same statement summing_double
    # carries: the collector is order-sensitive in fact, and the mark is one
    # conditional away from being applied to both forms by mistake. A caller who
    # knows their own merge commutes has unordered(), one level up.
    #
    # A caller-supplied map_supplier therefore never reaches this decision. The
    # 4-arg form always carries a merge_function (see the overload block), so it
    # is already excluded by the paragraph above, and the container gets no turn
    # to speak. That is why the rule grouping_by() states for its map_factory -
    # a caller-supplied container clears the mark, as to_collection() has it -
    # is absent here rather than merely unstated.
    #
    # The mark costs one thing, on the failure path. *Whether* a duplicate key
    # raises is a property of the multiset and does not change; which colliding
    # key IllegalStateException names can, under RACING, once two or more
    # distinct collisions are in play and no barrier orders their arrival.
    return Collector(_supply, _accumulate, finisher=_finish, characteristics=_ORDER_BLIND if merge_function is None else ())


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


async def _finish_groups(downstream: Collector[Any, Any, Any], groups: _M) -> _M:
    # Finishes in place and hands back the same mapping, rather than building a
    # dict: grouping_by()'s map_factory form has to return the caller's own
    # mapping type, and a rebuild into dict destroys it. The no-finisher path
    # used to return dict(groups), a copy - nothing references the box's mapping
    # once the collection ends, so dropping the copy isolates nothing less.
    finisher = downstream.finisher
    # the finisher is fixed for the whole collection, so the test belongs
    # outside the loop rather than once per group.
    if finisher is None:
        return groups
    # list(groups) rather than the mapping itself: rebinding an existing key
    # cannot resize a dict, but an arbitrary MutableMapping owes no such
    # guarantee, and the key list is one entry per group.
    for key in list(groups):
        groups[key] = await _maybe_await(finisher, groups[key])
    return groups


def _check_downstream(downstream: Collector[Any, Any, Any]) -> None:
    if not isinstance(downstream, Collector):
        raise StreamBuildException("downstream must be a Collector")


@overload
def grouping_by(classifier: Mapper[T, R]) -> Collector[T, Any, dict[R, Any]]: ...  # pragma: no cover


@overload
def grouping_by(
    classifier: Mapper[T, R], downstream: Collector[T, Any, Any]
) -> Collector[T, Any, dict[R, Any]]: ...  # pragma: no cover


@overload
def grouping_by(
    classifier: Mapper[T, R], map_factory: Supplier[_M], downstream: Collector[T, Any, Any]
) -> Collector[T, Any, _M]: ...  # pragma: no cover


def grouping_by(
    classifier: Mapper[T, R],
    map_factory: Any = _UNSET,
    downstream: Any = _UNSET,
) -> Collector[T, Any, Any]:
    # The form is chosen by *arity*, never by inspecting an argument's type -
    # the same dispatch reducing() uses above for the harder case where one
    # position carries three different meanings. Java puts mapFactory second,
    # and keeping it there costs nothing: a two-argument call can only be the
    # two-argument form, so grouping_by(f, to_set()) still binds to downstream
    # whatever to_set() happens to be. Sniffing isinstance(..., Collector)
    # instead would misbind a hand-rolled Collector-lookalike, and arity needs
    # no such judgement.
    if downstream is _UNSET:
        # Called as grouping_by(classifier) or grouping_by(classifier,
        # downstream): the second positional arg, if any, is the downstream,
        # and the container is the default dict.
        map_factory, downstream = dict, _TO_LIST if map_factory is _UNSET else map_factory
        supplied_factory = False
    else:
        supplied_factory = True
    # after the arity branch, so the 3-arg form rejects a non-Collector too
    _check_downstream(downstream)

    # async unconditionally, for the reason to_map()'s supplier is: it runs once
    # per collection rather than per element, so one path beats a sync fast one.
    async def _supply() -> _GroupBox:
        return _GroupBox(await _maybe_await(map_factory))

    async def _accumulate(container: _GroupBox, element: T) -> None:
        await _group_into(container, classifier, downstream, element)

    def _finish(container: _GroupBox) -> Any:
        return _finish_groups(downstream, container.groups)

    # Derives characteristics from the downstream, the same one keyword
    # mapping()/collecting_and_then() use. dict.__eq__ is key-order-insensitive
    # and compares values pairwise, and the classifier is a function of the
    # element alone, so any ordering of the same elements yields the same keys.
    # The result is therefore equal under reordering exactly when every group's
    # value is - which is the downstream's characteristic and nothing else. The
    # dict's own key iteration order does follow encounter order, and that is
    # no obstacle: UNORDERED promises equality, not iteration order.
    #
    # That derivation is bounded to the default dict container, and a supplied
    # map_factory clears the mark: it rests on dict.__eq__ ignoring key
    # insertion order, and a caller-supplied mapping type need not.
    # OrderedDict compared against another OrderedDict is equal only if its
    # keys went in in the same order, and key insertion order here follows the
    # order groups were first seen - which racing reorders. This is the rule
    # to_collection() already follows: a caller-supplied container declares
    # nothing.
    #
    # It keys on the factory being *supplied at all*, not on the type it
    # produces, so grouping_by(f, dict, ...) is cleared too. Deciding from the
    # type would mean either calling the factory here to look at what it returns
    # - it is a per-collection supplier and must not run early - or a
    # `map_factory is dict` whitelist, which answers nothing for any other type.
    # A caller who knows their chosen type's equality ignores key order has
    # unordered(), one level up.
    return Collector(
        _supply,
        _accumulate,
        finisher=_finish,
        characteristics=() if supplied_factory else downstream.characteristics,
    )


def partitioning_by(
    predicate: Predicate[T],
    downstream: Collector[T, Any, Any] = _TO_LIST,
) -> Collector[T, Any, dict[bool, Any]]:
    # Derives characteristics from the downstream, on its own structure rather
    # than grouping_by()'s: both partitions are seeded in the supplier before
    # any element arrives, so the result is the same two keys in the same order
    # over any input, the empty stream included. The value collected into each
    # partition is the only part that depends on encounter order, and that
    # dependence is exactly the downstream's characteristic.
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

    return Collector(_supply, _accumulate, finisher=_finish, characteristics=downstream.characteristics)


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
