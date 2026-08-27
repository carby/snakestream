## 1. The vocabulary in `collector.py`

- [x] 1.1 Add a `Characteristics` enum to `collector.py` with the single member
      `UNORDERED`. Its docstring must say why it has one member, not just that
      it does: `IDENTITY_FINISH` is already observable as `finisher is None`
      and a second statement of one fact can disagree with the first;
      `CONCURRENT` describes accumulating from independently reduced partitions,
      which no execution mode here produces (the `combiner` is never invoked),
      so nothing could read it. Name the roadmap's **Later** entry as where
      `CONCURRENT` belongs. **A reviewer reaching for "why not all three?" must
      find the answer here, not in this change's design.md** — the design is
      archived, the docstring ships.
- [x] 1.2 Add module-level `_NO_CHARACTERISTICS: frozenset[Characteristics] =
      frozenset()` as the shared empty default, with a comment giving both
      reasons for naming it rather than calling `frozenset()` in the signature:
      ruff B008, and letting the reader rule out the mutable-default bug on
      sight. Point at `collectors.py`'s `_TO_LIST`, which is the same move for
      the same reason.
- [x] 1.3 Add `characteristics` as `Collector.__init__`'s fifth parameter,
      after `finisher`, defaulting to `_NO_CHARACTERISTICS`; normalize any
      iterable to a `frozenset` on assignment; add the name to `__slots__`.
      Comment that appending rather than inserting is what keeps every existing
      positional call valid, and that `frozenset` is required rather than
      merely tidy — a `Collector` is spec'd reusable across concurrent
      collections, so a mutable set here would be its first mutable shared
      state.
- [x] 1.4 Extend `Collector`'s class docstring: it currently says the type
      "holds only these four callables, no per-collection state of its own",
      which this change falsifies as written. Say four callables plus one
      immutable datum, and that the datum is neither invoked nor awaited, so
      the sync-or-async rule the four parts carry does not reach it.
- [x] 1.5 **State in the `Characteristics` docstring that nothing in the
      library reads it yet**, and name what will: the roadmap's **Next** item 1
      (an ordered racing pipeline delivers in encounter order), where a
      terminal that does not observe order skips the reorder barrier. This is
      the single most misreadable thing in the change — an inert public field
      reads as dead code or as an unfinished edit — and a reviewer who does not
      know it is a prerequisite will either reject it or "fix" it by marking
      more factories. See task 4.2, which is the other half of that guard.

## 2. The declarations in `collectors.py`

- [x] 2.1 `to_set()` declares `UNORDERED`. Comment that it is the only factory
      in `Collectors` Java marks (`CH_UNORDERED_ID`), and that the declaration
      is true of the behaviour rather than asserted about it: a `set` retains no
      record of insertion order.
- [x] 2.2 `mapping()` passes `characteristics=downstream.characteristics`.
      One-line comment: the mapper runs per element and the result is the
      downstream's unchanged, so every trait of that result is the
      downstream's.
- [x] 2.3 `collecting_and_then()` passes `characteristics=
      downstream.characteristics`. Comment that the finisher runs once on the
      finished result, not per element, so it cannot introduce a dependence on
      arrival order. Note that Java additionally clears `IDENTITY_FINISH` here
      and that we do not, only because that member does not exist — so whoever
      adds it adds the clearing with it.
- [x] 2.4 Add a comment at **both** `grouping_by()` and `partitioning_by()`
      saying they take a downstream and deliberately do **not** derive from it,
      with the structural reason: the downstream's result is a map *value*, and
      a trait of the values says nothing about the map. `grouping_by(f,
      to_set())` builds a `dict` whose insertion order follows encounter order,
      so deriving `UNORDERED` from the inner `to_set()` would be wrong, not
      merely conservative. **Without this comment the omission reads as an
      oversight at exactly the two sites a reviewer will check first**, both
      taking a downstream and sitting next to two factories that do derive.
- [x] 2.5 Leave every other factory undeclared, and add one comment — at
      `counting()`, the most obviously order-blind of them — recording why:
      `counting`, `summing_*`, `averaging_*`, `summarizing_*`, `to_map`,
      `min_by`/`max_by`, `reducing` and `partitioning_by` are `CH_ID`/`CH_NOID`
      in OpenJDK, because Java's `UNORDERED` governs its combine strategy where
      an associative reduction is safe either way and the mark buys nothing.
      Under item 1 the mark *would* buy skipping the barrier here, which is a
      real divergence and item 1's to weigh, not this change's. **A reviewer
      comparing `to_set()` against `counting()` sees an inconsistency; this
      comment is what makes it a decision.** Note separately that `min_by`/
      `max_by` must never be marked regardless: `is_new_extremum()` keeps the
      earlier element on a tie, so which of two equal elements is returned is
      an encounter-order question.

## 3. Tests

- [x] 3.1 `tests/test_collector.py`: the `Characteristics` scenarios — the
      enum exposes `UNORDERED`; `IDENTITY_FINISH` and `CONCURRENT` are absent;
      a `Collector` built without `characteristics` reports an empty set and
      collects exactly as before; one built with `UNORDERED` reports it;
      declaring it changes no collected result.
- [x] 3.2 `tests/test_collector.py`: construction accepts a `list`, a `set` and
      a `frozenset` and stores a `frozenset` in each case.
- [x] 3.3 `tests/test_collect.py` (or `test_collector.py`, wherever the
      to_set/to_list assertions already sit): `to_set()` reports `UNORDERED`;
      `to_list()` and `joining()` do not. **The absence assertions are not
      padding** — they are what makes the "only `to_set()`" rule fail a test
      rather than depend on review, and they are the guard against task 2.5
      being undone later.
- [x] 3.4 `tests/test_mapping.py`: `mapping(len, to_set())` reports
      `UNORDERED`, `mapping(len, to_list())` does not, and
      `mapping(len, mapping(str, to_set()))` derives through both levels.
- [x] 3.5 `tests/test_collecting_and_then.py`: `collecting_and_then(to_set(),
      frozenset)` reports `UNORDERED`, `collecting_and_then(to_list(), tuple)`
      does not, and `collecting_and_then(mapping(len, to_set()), frozenset)`
      derives through both adapters.
- [x] 3.6 `tests/test_grouping_by.py` and `tests/test_partitioning_by.py`:
      assert neither reports `UNORDERED` even with an unordered downstream.
      This is the executable form of task 2.4's comment — the comment explains
      the omission, the test stops it being "corrected".

## 4. Documentation

- [x] 4.1 README: extend the `Collector(...)` prose at line 141 to the
      five-part signature, and add a `Collector.Characteristics` row to the
      Collectors table marking `UNORDERED` implemented and the other two
      intentionally deferred with the reason. The parity table is where a
      reader checks before assuming a Java member is missing (per CLAUDE.md),
      so a deferred member that is absent from it reads as an unnoticed gap.
- [x] 4.2 README: state plainly that no operation consults the characteristic
      yet. Pair with task 1.5 — one for the reader of the code, one for the
      reader of the docs. **Do not phrase either as though the field does
      something today.** An honest inert prerequisite survives review; an
      oversold one gets found out at the first grep for the attribute.
- [x] 4.3 CLAUDE.md: the Collectors section describes `Collector` as "a
      `supplier`/`accumulator`/`combiner`/`finisher` quadruple". Update it, and
      cite the sentence rather than a line number — the roadmap's standing note
      on stale prose, and `collapse-derive-wrappers`' demonstration of why.
- [x] 4.4 roadmap.md: annotate the **Next** item-4 entry with what landed, and
      confirm item 1's second table row (the mark-what-Java-leaves-unmarked
      divergence) still reads as open, since task 2.5 hands it there
      explicitly.

## 5. Validation

- [x] 5.1 `uv run ruff check .` and `uv run ruff format --check .` — expect
      B008 to be the rule task 1.2 is written against.
- [x] 5.2 `uv run ty check src`, including that `characteristics` normalizes to
      `frozenset[Characteristics]` from every accepted input type.
- [x] 5.3 `uv run pytest` and `uv run pytest --cov-fail-under=98`. If any new
      line needs a `pragma: no cover`, the field is under-specified rather than
      untestable — add the scenario instead of the pragma.
- [x] 5.4 `openspec validate add-collector-characteristics --strict`.
