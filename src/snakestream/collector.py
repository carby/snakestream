# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from typing import Any
from collections.abc import AsyncGenerator, Callable, Coroutine


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
