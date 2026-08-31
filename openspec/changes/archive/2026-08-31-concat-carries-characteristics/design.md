## Context

See proposal.md — Why. Three measured facts:

```
concat(a.parallel(), b.parallel()).is_parallel()        -> False
concat(a.unordered(), b.unordered())._is_ordered()      -> True
c = concat(a, b); await a.collect(...) -> [1,2,3]
                  await c.collect(...) -> [4,5]          # silent, no raise
```

All three come from one line: the result is `Stream(_concat(...), handlers)` —
a fresh base `Stream` with an empty chain and the default `SEQUENTIAL`. It
carries the operands' *elements* and their *close handlers*, and nothing else
they knew about themselves.

The one constraint that shapes the fix: `pipeline-immutability` states that "the
pipeline's ordering characteristic SHALL NOT be carried as separate state
alongside the chain", and `stream-ordering` defines the characteristic as a
positional fold over the chain. So the ordering half cannot be a field.

## Goals / Non-Goals

**Goals:**

- Java's `a ∥ b` for the executor and `a ∧ b` for ordering.
- Replace a silent wrong answer with `IllegalStateException`.
- State the base-`Stream` result as a decision.

**Non-Goals:**

- Making `concat()` return a subclass. Decided against and specified as such.
- Changing `iterator()`. Its non-destructive composition is a `stream-iterator`
  requirement with other callers (`collect(to_generator)`, `flat_map`); the
  invalidation belongs to `concat()`.
- Close handlers, laziness, element order — already correct and already spec'd.
- N-ary `concat`. Java's is binary; `a + b + c` chains through `__add__` in
  `implement-python-data-model` without needing one.

## Decisions

### Ordering is expressed as a stage, not as state

When either operand is unordered, `concat()` seeds the result's chain with the
same operation `unordered()` queues. The result is then unordered by the ordinary
fold, with no new state and no new code path.

*Alternative — an `_ordered` field on `Stream`, or an `initial` seed threaded
through `_is_ordered()`.* Rejected on the spec, not on taste:
`pipeline-immutability` forbids the field outright. The `initial` seed exists
already, but it exists for the racing split's re-entry, where a suffix's ordering
was decided by ops no longer in the list — a different problem, and widening it
to a constructor parameter would put a second source of truth beside the chain.

The seeding reads oddly at first — a chain the user did not build — but it is
correct in Java's own terms: `unordered()` is a *pipeline stage* there precisely
so that clearing order can be positional, and this is a stage the concatenation
itself introduces. A caller inspecting the result sees the reason for its
unorderedness in the place where reasons live.

### The executor is a field, because it always was

`a ∥ b` selects `RACING` or `SEQUENTIAL` and assigns it. No new mechanism: mode
is a value on the stream, position-independent by design, and a later
`sequential()`/`parallel()` still overrides it — which is the correct behaviour
and is specified, since a caller who wants the concatenation sequential should
not have to unpick how it got its mode.

The asymmetry between the two axes — one a field, one a stage — is not incidental
and is not new. It is the same asymmetry `stream-ordering` already documents:
ordering is positional, mode is not.

### `concat()` invalidates its operands, and does so itself

Setting the operands' consumed flag inside `concat()`, after the existing
`_check_not_consumed()` calls that `iterator()` performs.

*Alternative — have `iterator()` consume.* Rejected: `stream-iterator` requires
non-destructive composition, and `collect(to_generator)` and `flat_map` depend on
it. Fixing concat by breaking iterator trades one defect for three.

Java is the precedent rather than a nicety here: `AbstractPipeline` marks the
operands of `concat` as linked, and a later operation on one throws
`IllegalStateException`. The current behaviour is not a lenient divergence, it is
a wrong answer — the operand and the concatenation draw from one source, so
draining the operand removes elements from the concatenation's output with no
signal at all.

### The result stays a base `Stream`

Not fixed, stated. `type(a)` and `type(b)` may differ with no principled
tie-break; a subclass constructor may need arguments `concat()` cannot supply;
and Java returns an internal type for the same reason. The spec records it so the
next reader finds a decision instead of a silence — the failure mode roadmap
question 6 was made of.

Note that this holds *independently* of `derive-without-reinit`: even with
constructors no longer re-entered, `concat()` has no instance to copy from,
because it builds over two.

## Risks / Trade-offs

- **Operand invalidation is BREAKING for anyone relying on today's behaviour.**
  → Anyone relying on it is relying on a wrong answer: the only way to observe
  the old behaviour is to drain an operand and silently shorten the
  concatenation. Java raises. No deprecation path.
- **A concatenation is now parallel when only one operand was.** → Java's rule
  exactly, and the mode remains overridable. The alternative — requiring both —
  would silently sequentialise a pipeline half of which the caller asked to race.
- **Seeding a chain the caller did not write could confuse a reader inspecting
  the chain, or a future `__repr__`.** → `implement-python-data-model` adds that
  `__repr__`. The seeded stage is a truthful description of the pipeline, so it
  should show; worth a deliberate look when that change lands.

## Migration Plan

No deprecation path for the invalidation, per the risk above. The executor and
ordering changes need none: both strictly widen what the result can do, and no
pipeline that was correct before becomes incorrect.
