## Why

`Stream.is_ordered()` is public API that Java does not have. `BaseStream`
exposes exactly one piece of pipeline introspection — `isParallel()` — while the
ordering characteristic lives in the package-private `StreamOpFlag.ORDERED` and
is never readable by a caller. Under this project's guiding principle ("keep a
1:1 match on the *public API surface*, and exploit Python's capabilities
underneath"), a divergence in observable API surface is a defect rather than a
licensed shortcut: it is the same class of thing as the position-dependent
`.parallel()` bug that `make-ordering-a-chain-characteristic` fixed, minus the
wrong answer.

Now, because the three open `RACING` ordering items (ordered `sorted`, `limit`,
`skip`, `distinct`) each add call sites to this very function. Renaming after
they land means touching them twice.

## What Changes

- **BREAKING**: `Stream.is_ordered()` is renamed to `Stream._is_ordered()` and
  leaves the public API. Any caller using the public name breaks loudly with
  `AttributeError`. There is no deprecation shim — the project is pre-1.0 and
  handles breaks through the README migration log, as the two `0.3.5 -> next`
  ordering entries already do.
- **The mechanism is unchanged.** The fold over `Op.ordering` in `stream.py`
  keeps its body, its docstring and its semantics. Only the name changes.
- The one internal caller, `for_each_ordered()` in `stream.py`, moves to the
  private name. `find_first()` no longer branches on ordering — it has named
  `SEQUENTIAL` unconditionally since `make-ordering-a-chain-characteristic`.
- The `stream-ordering` spec stops asserting through the accessor wherever a
  behavioural observable exists. Nine scenarios currently state ordering *as*
  `is_ordered()` returning `True`/`False` because it was the only thing to look
  at; they are re-expressed against behaviour observable without it —
  `find_first()` on a racing pipeline, `sorted()` restoring order after
  `unordered()`, `for_each_ordered()`'s executor choice. A scenario keeps an
  accessor assertion only where no such observable exists, and then names
  `_is_ordered()` explicitly as an internal detail.
- Docs follow: the README parity row, a new README migration-log entry, and
  `CLAUDE.md`'s executor section.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-ordering`: the accessor named in the Purpose and in nine scenarios
  becomes internal, and the requirements are restated so the ordering
  characteristic is specified by what a pipeline *does* rather than by what an
  accessor *returns*. No change to the ordering semantics themselves — what is
  ordered, what clears it, what restores it, and the survival of a mode switch
  are all unchanged.

## Impact

- `src/snakestream/stream.py` — the definition and its single internal call
  site, `for_each_ordered()`.
- `tests/` — ~20 references, chiefly in the ordering tests. Those that exist
  only to assert the accessor's return value are rewritten to assert the
  behaviour the spec now states, so this is a test *rewrite*, not a
  find-and-replace.
- `openspec/specs/stream-ordering/spec.md` — Purpose and nine scenarios.
- `README.md` — the `is_ordered()` parity row, and a new migration-log entry.
- `CLAUDE.md` — the executor section, which is **already stale**: it says
  `find_first()` consults the accessor, which stopped being true in
  `make-ordering-a-chain-characteristic`. Corrected here rather than left.
- `roadmap.md` — the **Now** entry moves to **Done** at archive time.
- No change to `execution.py`, `ops.py`, `sink.py`, or any other spec: nothing
  outside `stream.py` referenced the accessor.
