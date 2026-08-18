## Context

`type.py` defines functional-interface-style aliases used throughout `src/snakestream` for typing user-supplied callables. Three of them (`Mapper`, `Consumer`, `Filterer`) don't match how they're actually used or dispatched at runtime (see roadmap.md's Now #1 and proposal.md). This is a small, self-contained typing fix confined to `type.py` plus two call sites in `stream.py`.

## Goals / Non-Goals

**Goals:**
- Make `Mapper` and `Consumer` accurately declare sync-or-async support, matching `Predicate`/`Comparator`'s existing pattern and `map()`/`for_each()`'s actual `_maybe_await`-based dispatch.
- Remove `Filterer`, which is unreferenced dead code.
- Make `for_each()`/`for_each_ordered()` use the `Consumer` alias instead of duplicating an inline signature.

**Non-Goals:**
- No runtime/dispatch behavior changes — `_maybe_await` already handles both sync and async callables everywhere these aliases are used; only the declared types catch up to it.
- No changes to `Predicate`, `Comparator`, `FlatMapper`, or the terminal-op aliases (`Accumulator`, `BinaryOperator`, `Supplier`, `BiConsumer`, `NumberMapper`) — out of scope for this item.

## Decisions

- **`Mapper` becomes `Callable[[T], R | None | Awaitable[R | None]]`.** Mirrors `Predicate = Callable[[T], bool | Awaitable[bool]]`'s shape exactly, just applied to `Mapper`'s existing `R | None` return type rather than introducing a new pattern.
- **`Consumer` becomes `Callable[[T], None | Awaitable[None]]`.** A consumer is a side-effecting callback (Java's `Consumer<T>` returns `void`); its return value is never used by `peek()`, `for_each()`, or `for_each_ordered()`, so the alias should say `None`, not `T`.
- **`for_each`/`for_each_ordered` (`stream.py`) switch from inline `Callable[[T], Any]` to `Consumer[T]`.** Removes a second, drifted definition of the same shape and matches how `peek()` already types its `consumer` parameter.
- **`Filterer` is deleted outright, not deprecated.** It's never imported or referenced anywhere in `src/` (`filter()` uses `Predicate`), so there's no call site to migrate and nothing to keep for compatibility.

## Risks / Trade-offs

- [Widening `Mapper`/`Consumer` to accept `Awaitable` could theoretically change type-checker results for existing call sites that pass a plain sync callable] → No risk: `Awaitable` is additive to the union (`R | None | Awaitable[R | None]` still accepts a bare sync return), so no previously-valid usage becomes invalid.
- [Deleting `Filterer` could break an external consumer importing it from `snakestream.type`] → Accepted: it's undocumented, unreferenced internally, and pre-1.0; consistent with how other dead-code removals in this codebase have been handled (see roadmap.md Done entries).

## Migration Plan

Single self-contained commit: edit `type.py`, update the two `stream.py` signatures, run `ty check src` and the full test suite to confirm no regressions. No data migration, no deprecation window — internal typing-only change with no runtime behavior difference. No rollback beyond a normal revert.
