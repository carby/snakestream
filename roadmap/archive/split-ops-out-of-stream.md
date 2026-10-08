+++
id = "split-ops-out-of-stream"
title = "Split the op/sink definitions out of `stream.py` into `ops.py`"
filed = 2026-08-19
closed = 2026-08-19
outcome = "shipped"
+++

**Split the op/sink definitions out of `stream.py` into `ops.py`.** The eight
op/sink pairs (`_FilterSink`/`_FilterOp` through `_SkipSink`/`_SkipOp`) moved
verbatim into a new `src/snakestream/ops.py`, leaving `stream.py` as the public
`Stream` API plus `PROCESSES`, `_UNSET` and `_concat`. `stream.py` went from
485 to 312 lines; `ops.py` is 199. The class bodies are byte-identical to what
they were in `stream.py` — verified by diffing the moved block against the
original lines before deleting them — so the whole change is the cut, the new
module's import header, and one import line in `stream.py`.

Sinks moved with their ops rather than staying behind: after the op-collapse
change each op is a two-to-four-line `_sink_cls = <its sink>` declaration, so
the pair is only readable together. The ops were not folded into `sink.py`
either — that file is the protocol (`Sink`, `Op`, `IntermediateSink`,
`TerminalSink`, `StatelessOp`/`StatefulOp`, `GeneratorBridgeSink`), and mixing
the concrete ops into it would re-create the same two-concerns-in-one-file
problem one module over.

No import cycle: `ops.py` imports from `sink.py`, `sort.py`,
`callable_dispatch.py` and `type.py` only. `_FlatMapSink` is the one op that
touches a `Stream`, and it does so purely by duck typing
(`self._flat_mapper(element)._compose()`); its `FlatMapper` annotation resolves
through `type.py`'s existing `TYPE_CHECKING` guard, so no guard was needed in
`ops.py`. `stream.py` shed `aclosing`, `merge_sort` and all seven `sink.py`
imports in the cut, keeping `check_comparator_result_type`, `is_async_callable`
and `isawaitable`, which the `Stream` API still uses.

Behavior-neutral, and no spec or README edit was needed: every moved name is
private and unexported, so no public API surface changed and neither
`sink-protocol` nor `pipeline-composition` describes which module the concrete
ops live in (they describe the protocol classes in `sink.py`). The change
therefore declared `skip_specs: true` and shipped no spec delta. The only test
edit was `tests/test_op_protocol.py`'s import of the eight op classes moving to
`snakestream.ops`; `tests/test_sequential.py` and `tests/test_sink.py` define
their doubles against `sink.py` and needed no change. 421 tests pass at 99%
coverage — identical to the pre-change run, with `ops.py` at 100%. The **Small
cleanups** item's `stream.py` line references were re-pointed to their new
lines. See
`openspec/changes/archive/2026-08-19-split-ops-into-ops-module`.
