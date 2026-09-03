## 1. Baseline

- [x] 1.1 Confirm the proposal's "no test changes expected" claim before touching anything: `grep -rn "_finish\|_create_container\|_UNSET\|_MinMaxSink\|_FindSink\|_ReduceSink" tests/` returns no hit that constrains this change. If it does, record which and treat it as a rename-only edit in task 5.1 rather than widening scope.
- [x] 1.2 Record the green baseline so any later failure is attributable: `uv run pytest` passes and the coverage figure it prints is noted for comparison in task 6.2.

## 2. The rule and its home (`sink.py`)

- [x] 2.1 Add `_unseeded(container)` immediately below `_UNSET`, returning `None if container is _UNSET else container`, with a docstring naming the rule ("an accumulation that never saw an element finishes as `None`") and stating why it is a function rather than five inlined comparisons — it is the only mechanism that reaches both `terminals.py`'s sinks and `collectors.py`'s closures, per design Decision 3. Verify by importing it and asserting `_unseeded(_UNSET) is None` and `_unseeded(0) == 0` in a scratch REPL.
- [x] 2.2 Add `_UnseededSink(TerminalSink[T])` below `TerminalSink`, supplying `_create_container() -> _UNSET` and `_finish() -> _unseeded(container)`, with a docstring stating the shape it names ("a terminal that starts with no value") and pointing at design Decision 1 for why the rule is not on `TerminalSink`'s default. Verify `uv run ty check src` still passes — the class must stay generic in `T`.
- [x] 2.3 Confirm nothing above the line in design Decision 1's table was touched: `_CountSink`, `_ForEachSink`, `_MatchSink`, `_CollectorSink` and `GeneratorBridgeSink` still derive from `TerminalSink` directly and still inherit the identity `_finish`. Verify by `grep -n "class .*Sink" src/snakestream/*.py` and reading the base of each.

## 3. The three sinks (`terminals.py`)

- [x] 3.1 Re-base `_MinMaxSink` on `_UnseededSink` (second position, after `AsyncDispatch`) and delete both its `_create_container` and its `_finish`. Verify `uv run pytest tests/ -k "min or max"` passes, including the empty-source cases that must still return `None`.
- [x] 3.2 Re-base `_FindSink` on `_UnseededSink` and delete both its `_create_container` and its `_finish`; its `__init__`, `accept` and `cancellation_requested` are untouched. Verify `uv run pytest tests/ -k "find"` passes, covering `find_first()`/`find_any()` over an empty source.
- [x] 3.3 Re-base `_ReduceSink` on `_UnseededSink` and delete its `_finish` **only** — it keeps `_create_container() -> self._identity`, per design Decision 2. Verify `uv run pytest tests/ -k "reduce"` passes, covering both the seeded and the no-identity overload over an empty source.
- [x] 3.4 Assert the MRO risk from design is actually closed rather than assumed: for `_MinMaxSink` and `_ReduceSink` (both mixing in `AsyncDispatch`), confirm `super().__init__()` still reaches `TerminalSink.__init__` — check `type(sink).__mro__` in a REPL and that `_container`/`_result` are initialized after construction.

## 4. The two collectors (`collectors.py`)

- [x] 4.1 Import `_unseeded` from `snakestream.sink` alongside the existing `Box, _UNSET` import, and replace `_extremum()`'s `_finish` body with `_unseeded(container.found)`. Verify `uv run pytest tests/ -k "min_by or max_by"` passes, including the empty-source `None`.
- [x] 4.2 Replace `reducing()`'s `_finish` body with `_unseeded(container.acc)`. Verify `uv run pytest tests/ -k "reducing"` passes across all three arities, including the empty-source `None` for the no-identity form.
- [x] 4.3 Confirm the `_UNSET`-seed logic inside both `accept()`/`_accumulate()` bodies is byte-identical to before — only the finish half collapses (proposal, "not in scope"). Verify with `git diff src/snakestream/collectors.py` showing changed lines only inside the two `_finish` closures and the import.

## 5. Prose that now says the wrong thing

- [x] 5.1 Narrow `_ReduceSink`'s docstring: the "implemented twice ... keep the two in step by hand" warning currently covers both the `_UNSET`-seed rule and the empty-finishes-as-`None` rule. The second half stops being duplicated here, so the warning must name only the seed rule and the measured +70% that keeps it duplicated. The pointer to `reducing()` and to `collapse-terminal-collector-duplication` stays.
- [x] 5.2 Make the same narrowing in `reducing()`'s docstring, which states the pairing from the other side ("the same empty-finishes-as-None rule"). Verify both docstrings now agree on exactly which rule is still duplicated.
- [x] 5.3 Confirm no `CLAUDE.md` edit is owed — it describes the Op/Sink protocol but names no `_finish`, and every name added here is underscore-private. Verify by `grep -n "_finish\|_create_container\|TerminalSink" CLAUDE.md` and reading any hit.
- [x] 5.4 Confirm no README edit is owed: no public API is added, renamed or removed, so the parity tables are unaffected and the Migration log takes no entry (that log is for breaking changes; this one is invisible to callers). Verify by `git diff --stat` showing no README change and no `src/snakestream/__init__.py` change.

## 6. Gates

- [x] 6.1 `uv run ruff check .` and `uv run ruff format --check .` both pass, including on this change's markdown.
- [x] 6.2 `uv run pytest` passes with no test file modified, and `uv run pytest --cov-fail-under=98` passes — coverage must not fall, since the five deleted bodies were all covered and `_unseeded()` inherits their coverage. Compare against the figure noted in task 1.2.
- [x] 6.3 `uv run ty check src` passes. Watch specifically for `_UnseededSink`'s generic parameter and for `_ReduceSink`'s narrowed `_create_container` return type.
- [x] 6.4 Do **not** benchmark this change, per design Decision 5. If a reviewer asks for a figure, point at that decision: `_finish` runs once per collection, so a ns/element number would measure noise and banking one would imply a gate that does not exist.

## 7. At archive

- [x] 7.1 Remove the roadmap's **Now** entry "1. The unseeded-accumulation rule is written five times" (under "Surfaced 2026-09-02, by the `sort-mixed-lane-by-successive-passes` read"), and renumber the sibling `_guarded()` item to 1. Verify the section's "Ranked as listed" line still reads correctly with one item left.
- [x] 7.2 Add a **Done** entry recording what was collapsed, that it carried no behaviour change and no spec delta (`skip_specs`), and — the part **Done** exists for — that design Decision 1 answered the roadmap's open question and design Decision 3 took a documented exception to the thin-helper preference, with the reason. A later reader must not re-derive either.
- [x] 7.3 File the fresh finding this change's exploration turned up but declined, so it is not re-derived: `_sort_by_key`'s `len(columns) == 1` lane is character-for-character the general lane at `last = 0` (verified identical on 8,000 randomized cases including ties and null-tolerant `(present, key)` tuples, both directions), but collapsing it costs ~0.2 us/sort of fixed `zip(*columns)` overhead — +18.6%/+18.8% at n=4, noise-dominated at n=20,000 — on the lane every plain `comparing()` call takes. Record it as declined-on-measurement, not as available work.
