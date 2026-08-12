from inspect import isawaitable
from typing import Any
from collections.abc import Callable


async def _maybe_await(fn: Callable, *args: Any) -> Any:
    result = fn(*args)
    return await result if isawaitable(result) else result
