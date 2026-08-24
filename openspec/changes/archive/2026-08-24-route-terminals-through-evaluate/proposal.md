## Why

`_evaluate()`'s docstring (`stream.py:112-116`) calls itself "the one place a
stream's execution mode is consulted", but two terminals bypass it and
hand-roll the same body: `for_each_ordered()` (`stream.py:292-294`) and
`find_first()` (`stream.py:300-305`) each call `self._check_not_consumed()`
and then `SEQUENTIAL.value(self._chain, self._stream, sink)` directly. That
makes three drive sites instead of one, contradicting the docstring a reader
is trusting, and `self._chain, self._stream` is spelled out separately at
each site. This is **Now** item 1 on `roadmap.md`, the highest-value item in
the 2026-08-24 legibility batch and the one the batch's other two `stream.py`
items (2 and 3) read against.

## What Changes

- Give `_evaluate()` an optional `executor: Executor | None = None` parameter;
  when omitted it consults `self._executor` as today.
- `for_each_ordered()` and `find_first()` call `self._evaluate(sink,
  SEQUENTIAL)` instead of hand-rolling `_check_not_consumed()` +
  `SEQUENTIAL.value(...)`.
- No behaviour changes: both terminals still force sequential/ordered
  execution regardless of the stream's mode; `find_first()` keeps its
  `is_ordered()` short-circuit to `find_any()` unchanged.
- Check `stream-find-first` spec's wording ("achieve this by naming the
  sequential executor explicitly for its own drive") still holds after the
  edit — passing `SEQUENTIAL` as an `_evaluate()` argument still satisfies it,
  so no delta is expected, but nudge the wording directly if it reads as
  naming the old call shape.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — this is a private-surface refactor; `skip_specs: true` is set in
`.openspec.yaml`. No externally observable behaviour changes: both terminals
keep forcing `SEQUENTIAL` execution, `find_first()` keeps its ordering
short-circuit, and no public API signature changes.)

## Impact

- `src/snakestream/stream.py`: `_evaluate()` gains an optional parameter;
  `for_each_ordered()` and `find_first()` bodies shrink to one call each.
- `openspec/specs/stream-find-first/spec.md`: wording check only, per the
  roadmap note — a direct edit if needed, not a delta (no requirement
  changes).
- Tripwire: full suite must pass with **no test file edited** (per
  `roadmap.md`'s shared brief for this batch). Off the per-element path, so
  no benchmark gate.
