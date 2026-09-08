## Why

`Stream.of()`'s meaning depends on how many arguments it is given.
`Stream.of([1, 2])` spreads the list into two elements; `Stream.of([1, 2], [3, 4])`
yields two lists. The number of arguments changes what the arguments *mean*,
there is no way to express a stream of exactly one iterable, and Java's
`of(T...)` treats every argument atomically. Roadmap item
`stream-of-arity-semantics` was unblocked on 2026-09-08 with the call made:
**Java parity wins**, and the break is accepted rather than argued down.

The divergence is not confined to one row. It is the primary documented idiom -
used in nearly every README example, throughout the test suite, in 25 live
capability specs, and by `Stream.iterate()`'s own body - which is why it has
stayed open since 2026-08-20 rather than being fixed in passing.

## What Changes

- **BREAKING**: `Stream.of(*args)` becomes atomic at every arity. `Stream.of([1, 2])`
  yields one element, the list. The `len(args) == 1` branch is deleted, not
  relocated; the whole body becomes `return Stream(list(args))`.
- **BREAKING**: `Stream.of(x)` for any iterable `x` - list, tuple, set, generator,
  async generator, iterator, async iterator - changes from spreading to a single
  element. This break is **silent**: results change, nothing raises.
- `Stream(source)`, the normalizing constructor, becomes the documented way to
  build a stream from a source. It is not new, not modified, and already the only
  name `snakestream/__init__.py` exports - the change stops concealing it.
- `Stream.iterate()` is rebuilt off the constructor (`Stream(gen)`), since
  `Stream.of(*gen)` would drain an infinite generator eagerly.
- README documents source construction in prose, on the precedent already set for
  Python's data model, rather than as a parity row. `of()`'s row loses ~8 lines of
  divergence text and becomes a match for Java.
- Every call site migrates mechanically: `Stream.of(X)` -> `Stream(X)` for
  single-argument calls, which is behaviour-preserving by construction because
  `of`'s single-argument branch *is* `Stream(args[0])` today.

Non-goals:

- No new API. Nothing is added; one branch is removed and an existing public name
  is documented.
- No typing work. All three construction forms infer `Stream[Unknown]` under `ty`
  today, so the migration is statically neutral. That `generic-stream-typing`'s
  first scenario claims otherwise is a pre-existing defect, recorded here and left
  alone.
- No change to the scalar set (`dict`, `str`, `bytes`, `bytearray`, `memoryview`)
  or to normalization behaviour of any kind.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-construction`: the "Stream.of() argument arity" requirement loses its
  "Single argument" scenario and generalizes "Multiple arguments" to every arity.
  The scalar-source and iterable-spreading requirements are unchanged in substance
  but rebase their scenarios onto `Stream(...)`, because after the split those
  scenarios no longer exercise normalization when written against `Stream.of(...)` -
  `of` is atomic by construction and would satisfy them vacuously.

## Impact

**Source** - three lines. `src/snakestream/stream.py`: `of()`'s arity branch and
`iterate()`'s return.

**Call sites** - 1,112 occurrences of `Stream.of(` outside the archive, of which
1,084 are single-argument. Every one sits on a single line; none spans a line
break, so the sweep is a regex rather than a rewrite.

```
1112 total  |  1084 one-arg  -> Stream(...)
            |    18 zero-arg  \  unchanged
            |    10 multi-arg /
```

**Excluded from the sweep, deliberately:**

- `roadmap/decisions.md` - append-only history.
- `README.md` under `## Migration` (6 sites) - historical prose recording breaks
  that were genuinely made against `Stream.of`; rewriting them falsifies the record.
- `openspec/changes/archive/**`.
- The 22 single-argument calls whose argument is in the scalar set. Nine of them are
  tests in `tests/test_of.py` that guard the `define-and-guard-stream-sources`
  decision, including a documented *silent* break; swept onto atomic `of()` they
  would still pass while testing nothing.

**Tests** - `tests/test_of.py` splits three ways: arity tests stay on `of()` and gain
coverage of the new atomic single-argument case; five normalization tests move to
`Stream(...)`; nine scalar-set tests move to `Stream(...)` to stay meaningful.
The rest of `tests/` is mechanical and guarded by the suite.

**Docs** - README's `of()` row, three passages that argue *from* `Stream.of()` being
the source entry point (the `generate()` section, `generate()`'s parity row, and
`ordered()`'s parity row), nine live examples, a new sources section, and a
Migration entry.

**Specs** - `stream-construction` takes the requirement delta. A further 24 live
specs use `Stream.of([...])` in scenario prose as an incidental example; whether
that sweep rides along or fans out into per-capability deltas is an open question
carried into `design.md`.
