# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from typing import Any
from collections.abc import AsyncGenerator, Callable, Coroutine

from snakestream.callable_dispatch import _maybe_await
from snakestream.type import NumberMapper


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
