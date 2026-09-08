## Why

`UNSET` in `sink.py` is two sentinels wearing one name. It means **"no value
yet"** — the seed of an unseeded fold, paired with `unseeded()` and
`UnseededSink` — and it separately means **"argument omitted"**, the ordinary
`_MISSING = object()` idiom used for arity dispatch across eight
default-argument slots in `Stream.reduce()`, `collectors.reducing()` and
`collectors.grouping_by()`. A reader has to infer which meaning is in play from
the neighbourhood.

The two roles are not merely confusable; the conflation is **load-bearing and
hiding four bugs**. Arity dispatch is written as a test of the *leading* slot
rather than of *which* slots were supplied, so every documented overload
spelled with a keyword misbehaves — silently rescued in one case by the shared
sentinel, and broken outright in the rest:

```
Stream.reduce(accumulator=f)                 -> correct, but ONLY because the
                                                two sentinels are one object
collect(reducing(binary_operator=op))        -> TypeError: 'object' object is not callable
collect(reducing(identity=0, binary_operator=op))  -> TypeError: 'int' object is not callable
collect(reducing(0, binary_operator=op))     -> TypeError: 'int' object is not callable
collect(grouping_by(f, downstream=to_set())) -> TypeError: 'object' object is not callable
```

`collector-grouping-by` already requires the form to be "selected by how many
arguments are passed", and `grouping_by(f, downstream=to_set())` passes two, so
that last line is a straight defect against a shipped spec. Splitting the
sentinel is what forces the dispatch to be written correctly, which is why the
rename and the fix belong in one change rather than two.

## What Changes

- Introduce a private `_MISSING = object()` **separately in `stream.py` and in
  `collectors.py`**, and convert the eight arity slots to it. The duplication is
  deliberate: every `is _MISSING` test compares against a default the same
  module wrote in the same function, so its identity never crosses a module
  boundary — unlike `UNSET`, which `stream.py` writes for `terminals.py`'s
  `ReduceSink` to read. Two distinct objects are therefore correct, and the
  naming rule underscores each. A comment at each definition states why.
- Retain `UNSET` in `sink.py` as the seed sentinel alone. Nothing moves into or
  out of `sink.py`; its stale comment is corrected in place.
- Rewrite arity dispatch in all three functions to branch on **which** slots are
  unsupplied rather than on the leading one, so each documented overload behaves
  identically whether spelled positionally or by keyword. **This fixes four
  defects.**
- Make the one place the two sentinels still meet explicit: a single normalizing
  line, `if identity is _MISSING: identity = UNSET`, after the arity branch. The
  coincidence becomes a stated rule.
- Reject a call whose supplied slots match no documented overload with
  `StreamBuildException` instead of failing later with a confusing `TypeError`
  or a misdirected message (`reduce(accumulator=f, combiner=g)`,
  `reducing(mapper=m, binary_operator=op)`, `grouping_by(f, map_factory=dict)`).
- Close roadmap item `unset-dual-role`; restate the resolved conditional in
  `sink-sentinel-placement`, which stays queued.

No public name is added, removed or renamed. The overload sets are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reduce-without-identity`: overload dispatch is by *supplied slots*, so
  `reduce(accumulator=f)` selects the no-identity form by rule rather than by
  sentinel coincidence; a supplied-slot set matching no overload raises
  `StreamBuildException`.
- `collector-reducing`: replaces "strictly by positional argument count … with
  no keyword-only disambiguation required", whose current wording can be read as
  licensing the three defects above, with dispatch by supplied slots; keyword
  spellings of each overload behave identically to their positional spellings.
- `collector-grouping-by`: the existing "selected by argument count" requirement
  gains the keyword spellings it already implies, and an explicit rejection for
  `map_factory` without `downstream`.

## Impact

- `src/snakestream/stream.py` — `Stream.reduce()` dispatch and `_MISSING`.
- `src/snakestream/collectors.py` — `reducing()` and `grouping_by()` dispatch
  and `_MISSING`; the eight slot defaults.
- `src/snakestream/sink.py` — comment only; `UNSET`, `unseeded()` and
  `UnseededSink` are untouched.
- `src/snakestream/terminals.py` — docstring references to the sentinel's dual
  role.
- Tests — keyword-form coverage for all three functions, and the invalid
  slot-set rejections.
- `README.md` — a Migration entry is owed for the behaviour fix.
- `roadmap/` — `unset-dual-role` closes into `decisions.md`;
  `sink-sentinel-placement` is edited in place and stays open.

**Explicitly out of scope:** where `UNSET`, `unseeded()` and `UnseededSink`
live. That is `sink-sentinel-placement`, whose remaining question this change
narrows but does not answer.
