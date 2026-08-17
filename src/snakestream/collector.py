# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from typing import Any, cast, overload
from collections.abc import AsyncGenerator, Callable, Coroutine

from snakestream.callable_dispatch import _maybe_await
from snakestream.sort import check_comparator_result_type
from snakestream.type import (
    R,
    T,
    BinaryOperator,
    Comparator,
    Mapper,
    NumberMapper,
)

_UNSET = object()


async def to_generator(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
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
        async for n in composition:
            total += await _maybe_await(mapper, n)
        return total

    return _sum


def summing_long(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, int]]:
    async def _sum(composition: AsyncGenerator[Any, None]) -> int:
        total = 0
        async for n in composition:
            total += await _maybe_await(mapper, n)
        return total

    return _sum


def summing_double(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _sum(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        async for n in composition:
            total += float(await _maybe_await(mapper, n))
        return total

    return _sum


def averaging_int(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        async for n in composition:
            total += await _maybe_await(mapper, n)
            count += 1
        return total / count if count else 0.0

    return _average


def averaging_long(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        async for n in composition:
            total += await _maybe_await(mapper, n)
            count += 1
        return total / count if count else 0.0

    return _average


def averaging_double(
    mapper: NumberMapper,
) -> Callable[[AsyncGenerator[Any, None]], Coroutine[Any, Any, float]]:
    async def _average(composition: AsyncGenerator[Any, None]) -> float:
        total = 0.0
        count = 0
        async for n in composition:
            total += await _maybe_await(mapper, n)
            count += 1
        return total / count if count else 0.0

    return _average


async def _extremum(composition: AsyncGenerator[T, None], comparator: Comparator[T], asc: bool) -> T | None:
    async def compare(a: T, b: T) -> int:
        sign = await _maybe_await(comparator, a, b)
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
        async for n in composition:
            value = n if mapper is None else await _maybe_await(mapper, n)
            if acc is _UNSET:
                acc = value
                continue
            acc = await _maybe_await(binary_operator, acc, value)
        return None if acc is _UNSET else acc

    return _reduce
