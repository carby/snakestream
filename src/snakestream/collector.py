# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from __future__ import annotations

from typing import Any
from collections.abc import AsyncGenerator


async def to_generator(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    async for n in composition:
        yield n


async def to_list(composition: AsyncGenerator) -> list[Any]:
    ret = []
    async for n in composition:
        ret.append(n)
    return ret
