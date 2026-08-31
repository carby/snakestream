## 1. Give the tables their third state

- [x] 1.1 Add a short paragraph above the `### Stream` table stating what the
      three row states mean (`x` implemented, struck through deliberately
      skipped, unmarked not yet implemented) and that the tables are total over
      Java 8's surface, so a Java 8 method with no row is a defect in the table.
- [x] 1.2 In the same paragraph, state that the tables cover `Stream` and
      `BaseStream` only, and that `IntStream`/`LongStream`/`DoubleStream` and
      `StreamSupport` are skipped wholesale for the reason `map_to_int`'s row
      gives — so the six primitive-specialization skip rows read as consequences
      of one decision. See design.md decision 3.

## 2. Complete the Stream table

- [x] 2.1 Add rows for `close()` and `on_close()`, both implemented, pointing at
      the Auto Close section for the `contextlib` pairing.
- [x] 2.2 Add an unmarked row for `reduce(identity, accumulator, combiner)` —
      **gap 1** — saying the two shipped overloads cover the fold and the third
      exists in Java to merge independently-reduced partitions, which this
      library does not produce.
- [x] 2.3 Add a struck-through row for `spliterator()` naming the roadmap
      **Later** entry it is already parked in, so the README stops being the one
      place that does not mention it.
- [x] 2.4 Add a struck-through row for `Optional`, stating the skip and its
      reason: `None` plus `is None` answers the membership question, and the
      chaining half is a second fluent layer nothing here needs. Record that
      implementing it would be a return-type break on four terminals plus
      `reduce()`, so it wants its own proposal. See design.md decision 4.
- [x] 2.5 Correct the `Optional[T]` return cells on `find_any()`, `find_first()`,
      `max()` and `min()` to `T | None`, and rewrite the Java-vocabulary phrases
      in their summaries ("an Optional describing…", "an empty Optional") to say
      what the code returns. Leave every other clause in those four summaries
      alone — the tie-break and encounter-order text is current.

## 3. Complete the Collectors table

- [x] 3.1 Add an unmarked row for `to_map(k, v, merge, map_supplier)` — **gap
      2** — naming the fourth argument as the result-container choice.
- [x] 3.2 Add an unmarked row for `grouping_by(classifier, map_factory,
      downstream)` — **gap 3** — same argument, and note that a caller-chosen
      mapping type interacts with the `UNORDERED` derivation the existing
      two-argument form performs.
- [x] 3.3 Add struck-through rows for `grouping_by_concurrent` and
      `to_concurrent_map`, each pointing at the `Characteristics` row's
      statement that `CONCURRENT` is not implemented rather than re-arguing it.
- [x] 3.4 Add a struck-through row for `Collector.of(...)` recording that the
      `Collector(...)` constructor is the equivalent and nothing is missing.

## 4. Complete the Comparator table

- [x] 4.1 Add an unmarked row for `then_comparing(comparator)` — **gap 4** —
      distinguishing it from the two `thenComparing` overloads already rowed:
      the key-extractor form is implemented, the `(f, key_comparator)` form is
      declined with a stated reason, and this third one has never been
      addressed. Note the tension it has to resolve: `KeyComparator` relies on
      "every segment yields a key" to keep the sort fast path total, which is
      the same invariant the declined overload would have broken.
- [x] 4.2 Add an unmarked row for `nulls_first` / `nulls_last` — **gap 5** —
      recording the non-parity argument: `sorted()` over a stream containing
      `None` raises `TypeError` today and there is no way to place the `None`s.
- [x] 4.3 Add struck-through rows for `comparing_int/long/double` and
      `then_comparing_int/long/double`, pointing at `map_to_int`'s no-boxing
      rationale.

## 5. Stop asserting a signature that does not exist

- [x] 5.1 Correct `collector.py`'s `Collector` docstring (around line 85): it
      names "`collect(supplier, accumulator, combiner)` and `reduce()`'s
      `combiner`" as precedents for an inert parity argument. Only `collect()`
      has one. Verify against `stream.py:352-365` before editing.
- [x] 5.2 Split the `roadmap.md` **Later** entry that bundles the two: the
      `collect()` half keeps its text and its real-parallelism blocker; the
      `reduce()` half is removed from there and becomes gap 1 in the new queue,
      with its open question restated as "is signature parity worth a parameter
      documented as inert?" rather than "is real parallelism decided?". See
      design.md decision 5.

## 6. Put the five gaps on the roadmap

- [x] 6.1 Add the five as **Queued changes** in **Now**, each one line naming
      the Java method, the module it would land in, and the question it has to
      answer. Keep them five entries, not one batched entry — design.md decision
      6 records why, and the batching decision belongs to whoever picks them up.
- [x] 6.2 Mark gap 5 as the one with an argument already attached, so a later
      session does not have to rediscover that it is the only member of the
      queue with a user-facing bug behind it.
- [x] 6.3 Close **Now** item 5, recording its answer: README was credited with
      tracking a set it had no way to express, the audit found five real gaps,
      and the fix was structural (a third row state) rather than a one-off list.
      Record the audit's totals — 33 `Stream` methods implemented, 27 of 33
      `Collectors`, 3 of the `Comparator` surface — so the next reader can see
      the shape without re-deriving it.
- [x] 6.4 Answer the Java 9 gate in the same entry: none of the five is
      structural, and the two genuinely blocked items (`spliterator()`, the
      `collect()` combiner) are parked behind a decision **Later** says needs
      explicit buy-in — so they cannot be what Java 9 waits on. Update the
      Java 9 **Later** entry to point at this finding instead of at "the
      **Now**/**Next** buckets are still closing out Java 8 parity gaps", which
      will no longer be true.
- [x] 6.5 Sweep the three places in `roadmap.md` that offer "the Java-8 parity
      gaps README still tracks as unimplemented" as a refill source and point
      them at the queue this change creates.

## 7. Validate and land

- [x] 7.1 Re-audit the finished tables against Java 8's `Stream`, `BaseStream`,
      `Collectors` and `Comparator` method lists one more time, top to bottom —
      the totality claim added in 1.1 is only worth making if it was checked
      after the last row was written, not before.
- [x] 7.2 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run ty check src`, and `uv run pytest --cov-fail-under=98`. Only a
      docstring changed in `src/`, so all five should pass untouched; a failure
      means something outside this change's scope was edited.
- [x] 7.3 Confirm `git diff -- tests/` is empty. That is the tripwire: this
      change alters no behaviour, so no test can need editing.
