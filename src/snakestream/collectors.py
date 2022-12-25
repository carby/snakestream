# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from typing import AsyncGenerator, Any, List


async def to_generator(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    async for n in composition:
        yield n


async def to_list(composition: AsyncGenerator) -> List[Any]:
    ret = []
    async for n in composition:
        ret.append(n)
    return ret
