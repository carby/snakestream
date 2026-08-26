## 1. Builtins in `execution.py` — story 2(a)

- [x] 1.1 Replace `await source.__anext__()` in `_guarded` (`execution.py:88`) with `await anext(source)`, leaving the surrounding lock/`StopAsyncIteration` structure untouched.
- [x] 1.2 Replace both `branch.__anext__()` calls in `race_through` (`:159` in the `in_flight` dict comprehension, `:172` in the re-arm) with `anext(branch)` / `anext(branches[branch])`.
- [x] 1.3 Confirm the `aiter(source)` comment at `:151` still reads correctly — it explains arity (one shared iterator), not the builtin swap, and must not be edited.

## 2. Stdlib shapes in `collectors.py` — story 2(b)

- [x] 2.1 Rewrite `_finish_groups` (`collectors.py:415-420`): hoist the loop-invariant `finisher is not None` test out of the loop, returning `dict(groups)` when there is no finisher, and express the finishing arm as an async dict comprehension over `groups.items()` (design Decision 7).
- [x] 2.2 Rewrite `partitioning_by._supply` (`collectors.py:452-456`) to build its two-key dict directly instead of looping over the `(True, False)` literal, keeping both suppliers awaited.
- [x] 2.3 Run `uv run pytest tests/` for the grouping/partitioning suites and confirm no test file needed editing.

## 3. Chain extension — story 2(c)

- [x] 3.1 `stream.py:128`: `self._chain + [op]` -> `[*self._chain, op]` inside `_extend`, leaving its docstring as is.

## 4. Type aliases — story 2(d)

- [x] 4.1 `type.py:24`: narrow `Mapper` to `Callable[[T], R | Awaitable[R]]`, dropping the `None` arm entirely (design Decision 2).
- [x] 4.2 `type.py:30` (`Consumer`) and `:37` (`BiConsumer`): move `None` to the tail of each union — `Awaitable[None] | None` — with no other change, since `None` is genuinely their return type.
- [x] 4.3 Run `uv run ty check src` and resolve any site that was leaning on `Mapper`'s optional by declaring `R` optional at that site, not by restoring the alias arm.
- [x] 4.4 Verify the delta spec's scenarios hold: a mapper declared `Callable[[int], str]` gives `Stream[str]`, and a mapper declared to return `str | None` still type-checks with `R` bound to `str | None`.

## 5. Module namespace — story 2(e)

- [x] 5.1 `__init__.py:11`: add `dist_name` to the `finally: del`, so the name created at `:6` is dropped alongside `version` and `PackageNotFoundError`.
- [x] 5.2 Verify `import snakestream; hasattr(snakestream, "dist_name")` is now `False` and `snakestream.__version__` still resolves.

## 6. The lint gate — story 2(f)

- [x] 6.1 Add a module-level `_TO_LIST = to_list()` in `collectors.py` and use it as the default for `grouping_by`'s and `partitioning_by`'s `downstream` parameter (`:430`, `:448`), clearing both `B008` findings (design Decision 3).
- [x] 6.2 Sort `Collector.__slots__` (`collector.py:42`) to clear `RUF023`.
- [x] 6.3 Add a rule-scoped `noqa: B004` at `callable_dispatch.py:14` with the reason: the line reaches for the class-level `__call__` to ask whether *it* is a coroutine function, which `callable()` cannot express and which is the only way an `async def __call__` instance classifies correctly.
- [x] 6.4 Add a rule-scoped `noqa: PERF203` at `stream.py:192`'s close-handler loop with the reason: catching per handler and continuing is the loop's contract, pinned by the `stream-close-handling` spec and `test_close_with_multiple_raising_handlers_runs_all_and_raises_first`.
- [x] 6.5 Widen `[tool.ruff.lint] select` in `pyproject.toml` from `["E","F","W","C90","UP"]` to add `ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW`, keeping `mccabe.max-complexity = 10`.
- [x] 6.6 Run `uv run ruff check .` and confirm it exits clean with the widened selection — every trial-run finding is now either fixed by groups 2-5 or suppressed in 6.3/6.4.
- [x] 6.7 Run `uv run ruff format --check .` to confirm the rewrites did not disturb formatting.

## 7. Verification

- [x] 7.1 Run the full suite: `uv run pytest`. It must pass with **no test file edited** — that is this change's tripwire (proposal, Impact).
- [x] 7.2 Run `uv run pytest --cov-fail-under=98` to confirm the coverage gate still passes.
- [x] 7.3 Run `uv run ty check src` clean.
- [x] 7.4 Confirm `git diff --stat` touches only `execution.py`, `collectors.py`, `collector.py`, `stream.py`, `type.py`, `callable_dispatch.py`, `__init__.py` and `pyproject.toml`, and that no hunk lands on a per-element path (design, Non-Goals).
- [x] 7.5 Update `roadmap.md`: move story 2 out of **Now** into **Done** with how each of (a)-(f) resolved, and note that `tests/`'s 61 findings — `PT011`'s three sites in particular — remain available to refill **Next**.
