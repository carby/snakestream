## Context

See `proposal.md` — Why. The relevant current state:

- `stream.py` lines 44–223 hold the eight op/sink pairs; lines 226–485 hold
  `Stream` (plus the module-level `PROCESSES`, `_UNSET`, and `_concat`).
- The op half's runtime dependencies are `sink.py` (`Counter`,
  `IntermediateSink`, `Op`, `Sink`, `StatefulOp`, `StatefulSink`, `StatelessOp`),
  `sort.py` (`merge_sort`), `callable_dispatch.py` (`is_async_callable`), and
  `type.py` aliases. None of these import `stream.py` at runtime.
- `_FlatMapSink` is the only op that touches a `Stream`, and it does so purely by
  duck typing: `self._flat_mapper(element)._compose()`. Its `FlatMapper` type
  alias resolves `Stream` under `type.py`'s `TYPE_CHECKING` guard, so the
  reference is annotation-only.

## Goals / Non-Goals

**Goals:**

- `ops.py` contains the eight op/sink pairs and nothing else; `stream.py`
  contains the public `Stream` API and nothing else.
- Byte-identical class bodies — the move must be reviewable as a cut-and-paste.

**Non-Goals:**

- Renaming, re-scoping, or re-exporting any op or sink. They stay private and
  unexported.
- Touching `sink.py`'s protocol classes, the terminal/collector layer, or
  anything the two remaining **Now** roadmap items cover.
- Moving `_concat`, `PROCESSES`, or `_UNSET`, which belong to the `Stream` half.

## Decisions

**Move the sinks along with the ops, not just the ops.** Each op is a two-to-four
line declaration whose only content is `_sink_cls = <its sink>`; separating the
pair would leave a module that cannot be read on its own. The roadmap item's
stated boundary (lines 45–223) is exactly the eight pairs.

*Alternative considered:* ops in `ops.py`, sinks staying in `stream.py`. Rejected
— it splits a pair that is meaningless apart and leaves `stream.py` still
carrying the execution layer, which is the thing being fixed.

**Name the module `ops.py`, matching the roadmap.** It names what is inside it
(the eight `Op` subclasses and their sinks), and it sits alongside `sink.py`,
which holds the protocol those classes implement.

*Alternative considered:* folding the eight pairs into `sink.py`. Rejected —
`sink.py` is the protocol (`Sink`, `Op`, `IntermediateSink`, `TerminalSink`,
`StatelessOp`/`StatefulOp`, `GeneratorBridgeSink`); mixing the concrete ops into
it re-creates the same two-concerns-in-one-file problem one module over.

**No runtime import cycle, so no `TYPE_CHECKING` gymnastics are needed.**
`stream.py` will import from `ops.py`; `ops.py` imports nothing from `stream.py`,
because `_FlatMapSink`'s only `Stream` contact is duck-typed and its `FlatMapper`
annotation resolves through `type.py`'s existing guard. Verified before the move
rather than assumed.

**Tests import the ops from their new home.** `tests/test_op_protocol.py` is the
only test importing the eight classes; its import moves from `snakestream.stream`
to `snakestream.ops`. `tests/test_sequential.py` and `tests/test_sink.py` define
their own doubles against `sink.py` and are untouched.

## Risks / Trade-offs

- **A stale import left in `stream.py` after the cut** (e.g. `merge_sort`,
  `aclosing`, `Counter`) → `ruff check` flags unused imports, and it runs in CI;
  run it locally as part of the change.
- **An import cycle appears anyway from something not spotted in the read** →
  caught immediately by the test suite, since importing `snakestream.stream` is
  the first thing every test does. If one did appear, the fallback is a
  `TYPE_CHECKING` guard in `ops.py`, the pattern `type.py` already uses.
- **Behavioral drift smuggled in by an "obvious" tidy-up during the move** →
  explicitly out of scope; anything tempting goes to the roadmap's remaining
  **Now** items, which are sequenced after this one precisely to sweep up such
  things.

## Migration Plan

Not applicable — no public API, no persisted data, no dependency change. Rollback
is reverting the commit.
