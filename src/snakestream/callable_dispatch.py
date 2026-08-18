from inspect import isawaitable, iscoroutinefunction
from typing import Any
from collections.abc import Callable


async def _maybe_await(fn: Callable, *args: Any) -> Any:
    result = fn(*args)
    return await result if isawaitable(result) else result


def is_async_callable(fn: Callable) -> bool:
    if iscoroutinefunction(fn):
        return True
    call = getattr(type(fn), "__call__", None)
    return call is not None and iscoroutinefunction(call)


# Canonical shape for the 26 per-element call sites classified via
# is_async_callable (see tasks.md section 2-4): hoist `is_async`/`checked`
# locals inside the per-composition generator body (never in the enclosing
# function, or classification leaks across compositions/branches), then:
#
#   is_async = is_async_callable(fn)
#   checked = False
#   async for i in iterable:
#       r = fn(i)
#       if is_async:
#           r = await r
#       elif not checked:
#           checked = True
#           if isawaitable(r):
#               is_async = True
#               r = await r
#       yield r
#
# The `elif not checked` branch is a one-time safety net: a callable with a
# plain `def __call__` that returns a coroutine classifies as sync but must
# still be awaited on its first (and, by the homogeneity contract, every)
# result.


def _classify_step(fn: Callable, is_async: bool, checked: bool, *args: Any) -> tuple[Any, bool, bool]:
    # Same per-element classification as the canonical shape above, factored
    # out (plain sync helper, no wrapper coroutine) for call sites that
    # classify several callables per element — e.g. reducing()'s mapper and
    # binary_operator, or to_map()'s key/value/merge — where inlining each
    # would push the enclosing function's branch count past the mccabe
    # complexity gate. The caller still performs the actual `await`.
    result = fn(*args)
    if is_async:
        return result, True, True
    if not checked and isawaitable(result):
        return result, True, True
    return result, is_async, True
