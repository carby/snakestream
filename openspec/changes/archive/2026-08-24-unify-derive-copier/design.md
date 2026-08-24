## Context

`stream.py` currently has two five-field copy bodies:

```python
def _derive(self, chain: list[Op]) -> Stream[Any]:
    self._check_not_consumed()
    new_stream = type(self)(self._stream, self._close_handlers)
    new_stream._chain = chain
    new_stream._ordered = self._ordered
    new_stream._executor = self._executor
    self._consumed = True
    return new_stream


def _derive_executor(self, executor: Executor) -> Stream[Any]:
    self._check_not_consumed()
    new_stream = type(self)(self._stream, self._close_handlers)
    new_stream._chain = self._chain
    new_stream._ordered = self._ordered
    new_stream._executor = executor
    self._consumed = True
    return new_stream
```

`_derive_executor()` carries a docstring warning that it must not compose the
chain and must not assign the new executor onto `self` — both properties are
what make `.parallel()`/`.sequential()` position-independent (see
`stream-execution-model` spec and the "Replaced the `Stream` ->
`ParallelStream` subclass" **Done** entry in `roadmap.md`). See
`proposal.md` - Why for the duplication risk this leaves.

## Goals / Non-Goals

**Goals:**
- One copier, `_derive(chain, executor)`, used by every call site that
  currently goes through either `_derive()` or `_derive_executor()`.
- Preserve check-then-copy-then-consume ordering exactly: a raising
  `_check_not_consumed()` must leave the receiver untouched and still valid.
- Preserve the "must not compose, must not assign onto self" warning by
  moving it onto `parallel()`/`sequential()`, the two call sites where
  getting this wrong would silently reintroduce position-dependence.

**Non-Goals:**
- No change to what fields `Stream` carries, or to `_check_not_consumed()`
  itself.
- No change to `parallel()`/`sequential()`'s public signatures or to any
  intermediate op's signature.

## Decisions

**One method with two parameters, not a shared private helper called by two
thin wrappers.** The roadmap's proposed shape (see `roadmap.md`, "Item 1, the
proposed shape") is a single `_derive(self, chain, executor)`. An alternative
of keeping `_derive(chain)` and `_derive_executor(executor)` as thin
wrappers around a new private `_copy(chain, executor)` was considered and
rejected: it keeps two public-to-the-class names and two call sites for
what is conceptually one operation, which is the same duplication risk one
level down — a third method could still be added to only one wrapper.

**Call sites after the merge:**
- The eight intermediate ops (`filter`, `map`, `flat_map`, `sorted`,
  `distinct`, `peek`, `limit`, `skip`) call
  `self._derive(self._chain + [op], self._executor)`.
- `parallel()` calls `self._derive(self._chain, RACING)`.
- `sequential()` calls `self._derive(self._chain, SEQUENTIAL)`.

`self._chain + [op]` must stay a fresh list (not `self._chain.append(op)`)
so the receiver's chain is never mutated — this is already true today and
must not regress.

**Docstring placement.** `_derive_executor()`'s docstring is the only part
of that method with content worth preserving (the merge itself is
mechanical). Rather than attach it to the unified `_derive()` — where a
reader deriving via an intermediate op would read a warning that only
applies to the executor-changing call sites — it moves onto `parallel()`
and `sequential()`, the two public methods whose correctness actually
depends on it.

## Risks / Trade-offs

- [A future intermediate op accidentally passes a different executor, or a
  future mode switch accidentally passes a composed chain] → The unified
  `_derive()` takes both fields as explicit required parameters with no
  defaults, so a call site omitting either fails at the call, not silently;
  the moved docstring on `parallel()`/`sequential()` documents *why* those
  two specific arguments matter.
- [Merging two methods into one with the same name as one of the originals
  could make review harder to scope] → Low risk here: the diff is small
  (one file, ~8 call sites, all mechanical), and the roadmap's tripwire
  (full suite green, no test file edited) is the verification story.

## Migration Plan

Not applicable — private, in-process refactor with no deployment or data
migration step. Land as a single commit; rollback is a plain revert.
