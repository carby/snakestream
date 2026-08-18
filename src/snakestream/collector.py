# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from contextlib import aclosing
from inspect import isawaitable
from typing import Any, cast, overload
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine

from snakestream.callable_dispatch import _classify_step, is_async_callable
from snakestream.sort import check_comparator_result_type
from snakestream.type import (
    R,
    T,
    BinaryOperator,
    Comparator,
    Mapper,
    NumberMapper,
    Predicate,
)

_UNSET = object()


async def to_generator(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    if hasattr(composition, "aclose"):
        async with aclosing(composition):
            async for n in composition:
                yield n
    else:
        async for n in composition:
            yield n


async def to_list(composition: AsyncGenerator) -> list[Any]:
    ret = []
    async for n in composition:
        ret.append(n)
    return ret


def joining(
    delimiter: str = "", prefix: str = "", suffix: str = ""
) -> Callable[[AsyncGenerator[str, None]], Coroutine[Any, Any, str]]:
    async def _join(composition: AsyncGenerator[str, None]) -> str:
        parts = []
        async for n in composition:
            parts.append(n)
        return prefix + delimiter.join(parts) + suffix

    return _join


def counting() -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, int]]:
    async def _count(composition: AsyncGenerator[Any, None]) -> int:
        count = 0
        async for _ in composition:
            count += 1
        return count

    return _count


# summing_int/summing_long and averaging_int/averaging_long/averaging_double
# are intentionally near-identical: Java's Collectors distinguishes them by
# primitive type (int/long/double), a distinction Python's numeric tower
# doesn't have. They're kept as separate functions to mirror the distinct
# Java method names, not left over from copy-paste.


def summing_int(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, int]]:
    async def _sum(composition: AsyncGenerator[Any, None]) -> int:
        total = 0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += cast(Any, r)
        return total

    return _sum


def summing_long(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, int]]:
    async def _sum(composition: AsyncGenerator[Any, None]) -> int:
        total = 0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += cast(Any, r)
        return total

    return _sum


def summing_double(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _sum(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += float(cast(Any, r))
        return total

    return _sum


def averaging_int(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += cast(Any, r)
            count += 1
        return total / count if count else 0.0

    return _average


def averaging_long(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += cast(Any, r)
            count += 1
        return total / count if count else 0.0

    return _average


def averaging_double(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        is_async = is_async_callable(mapper)
        checked = False
        async for n in composition:
            r = mapper(n)
            if is_async:
                r = await cast("Awaitable[int | float]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            total += cast(Any, r)
            count += 1
        return total / count if count else 0.0

    return _average


async def _extremum(composition: AsyncGenerator[T, None], comparator: Comparator[T], asc: bool) -> T | None:
    is_async = is_async_callable(comparator)
    checked = False

    async def compare(a: T, b: T) -> int:
        nonlocal is_async, checked
        sign = comparator(a, b)
        if is_async:
            sign = await cast("Awaitable[int]", sign)
        elif not checked:
            checked = True
            if isawaitable(sign):
                is_async = True
                sign = await sign
        sign = cast(int, sign)
        check_comparator_result_type(sign)
        return sign

    found = cast(T, _UNSET)
    async for n in composition:
        if found is _UNSET:
            found = n
            continue

        # comparator(n, found): negative if n orders before found, positive
        # if after. found (the earlier element) is kept on a tie.
        sign = await compare(n, found)
        is_new_extreme = sign < 0 if asc else sign > 0
        if is_new_extreme:
            found = n
    return None if found is _UNSET else found


def min_by(comparator: Comparator[T]) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, T | None]]:
    async def _min(composition: AsyncGenerator[T, None]) -> T | None:
        return await _extremum(composition, comparator, asc=True)

    return _min


def max_by(comparator: Comparator[T]) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, T | None]]:
    async def _max(composition: AsyncGenerator[T, None]) -> T | None:
        return await _extremum(composition, comparator, asc=False)

    return _max


@overload
def reducing(
    binary_operator: BinaryOperator[T],
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, T | None]]: ...  # pragma: no cover


@overload
def reducing(
    identity: T, binary_operator: BinaryOperator[T]
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, T]]: ...  # pragma: no cover


@overload
def reducing(
    identity: R, mapper: Mapper[T, R], binary_operator: BinaryOperator[R]
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, R]]: ...  # pragma: no cover


def reducing(identity: Any = _UNSET, mapper: Any = _UNSET, binary_operator: Any = _UNSET) -> Any:
    if mapper is _UNSET:
        # Called as reducing(binary_operator): the single positional arg is
        # the fold operator, with no identity and no element mapper.
        identity, mapper, binary_operator = _UNSET, None, identity
    elif binary_operator is _UNSET:
        # Called as reducing(identity, binary_operator): the second
        # positional arg is the fold operator, with no element mapper.
        mapper, binary_operator = None, mapper

    async def _reduce(composition: AsyncGenerator[Any, None]) -> Any:
        acc = identity
        has_mapper = mapper is not None
        mapper_is_async = is_async_callable(mapper) if has_mapper else False
        mapper_checked = False
        op_is_async = is_async_callable(binary_operator)
        op_checked = False
        async for n in composition:
            if has_mapper:
                value, mapper_is_async, mapper_checked = _classify_step(mapper, mapper_is_async, mapper_checked, n)
                if mapper_is_async:
                    value = await value
            else:
                value = n
            if acc is _UNSET:
                acc = value
                continue
            r, op_is_async, op_checked = _classify_step(binary_operator, op_is_async, op_checked, acc, value)
            if op_is_async:
                r = await r
            acc = r
        return None if acc is _UNSET else acc

    return _reduce


def to_map(
    key_mapper: Mapper[T, R],
    value_mapper: Mapper[T, Any],
    merge_function: BinaryOperator[Any] | None = None,
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, dict[R, Any]]]:
    async def _to_map(composition: AsyncGenerator[T, None]) -> dict[R, Any]:
        result: dict[R, Any] = {}
        key_is_async = is_async_callable(key_mapper)
        key_checked = False
        value_is_async = is_async_callable(value_mapper)
        value_checked = False
        merge_is_async = is_async_callable(merge_function) if merge_function is not None else False
        merge_checked = False
        async for n in composition:
            key, key_is_async, key_checked = _classify_step(key_mapper, key_is_async, key_checked, n)
            if key_is_async:
                key = await key
            value, value_is_async, value_checked = _classify_step(value_mapper, value_is_async, value_checked, n)
            if value_is_async:
                value = await value
            if key in result:
                if merge_function is None:
                    raise ValueError(f"Duplicate key: {key!r}")
                merged, merge_is_async, merge_checked = _classify_step(
                    merge_function, merge_is_async, merge_checked, result[key], value
                )
                value = await merged if merge_is_async else merged
            result[key] = value
        return result

    return _to_map


def to_set() -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, set[T]]]:
    async def _to_set(composition: AsyncGenerator[T, None]) -> set[T]:
        result: set[T] = set()
        async for n in composition:
            result.add(n)
        return result

    return _to_set


async def _generator_of(items: list[T]) -> AsyncGenerator[T, None]:
    for item in items:
        yield item


def grouping_by(
    classifier: Mapper[T, R],
    downstream: Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, Any]] = to_list,
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, dict[R, Any]]]:
    async def _grouping_by(composition: AsyncGenerator[T, None]) -> dict[R, Any]:
        groups: dict[R, list[T]] = {}
        is_async = is_async_callable(classifier)
        checked = False
        async for n in composition:
            key = classifier(n)
            if is_async:
                key = await cast("Awaitable[R]", key)
            elif not checked:
                checked = True
                if isawaitable(key):
                    is_async = True
                    key = await key
            groups.setdefault(cast(R, key), []).append(n)
        return {key: await downstream(_generator_of(items)) for key, items in groups.items()}

    return _grouping_by


def partitioning_by(
    predicate: Predicate[T],
    downstream: Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, Any]] = to_list,
) -> Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, dict[bool, Any]]]:
    async def _partitioning_by(composition: AsyncGenerator[T, None]) -> dict[bool, Any]:
        partitions: dict[bool, list[T]] = {True: [], False: []}
        is_async = is_async_callable(predicate)
        checked = False
        async for n in composition:
            r = predicate(n)
            if is_async:
                r = await cast("Awaitable[bool]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            partitions[bool(r)].append(n)
        return {key: await downstream(_generator_of(items)) for key, items in partitions.items()}

    return _partitioning_by
