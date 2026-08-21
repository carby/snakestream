Each group is independently revertable and can land on its own. Groups 1-3 are
behaviour-neutral and share one tripwire: **the full suite must pass with no
test file edited**. Group 4 is the breaking change and is deliberately last, so
that a failure there does not force a revert of the other three.

## 1. `_maybe_aclosing` as an `@asynccontextmanager` (part d)

- [x] 1.1 Confirm an existing test drives an exception (or an early `break`,
      e.g. `limit`/`find_any`) through a source wrapped by `_maybe_aclosing`
      and asserts `aclose()` still ran. If none does, add one first — it is the
      only thing that catches a missing `finally`.
- [x] 1.2 Replace the `_maybe_aclosing` class in `base_stream.py` with the
      `@asynccontextmanager` generator from design.md, keeping the
      `try`/`finally`, the `hasattr(thing, "aclose")` guard and the name.
      Import `asynccontextmanager` from `contextlib`.
- [x] 1.3 Run the full suite: green, no test file edited. Run `ruff check`,
      `ruff format --check` and `ty check src`.

## 2. Race-loop cleanups in `_parallel()` (part b)

- [x] 2.1 Record a baseline for parallel throughput on the current code
      (established harness: Python 3.14, 20,000 elements, best of 5, three
      independent invocations) so 2.4 has something to compare against.
- [x] 2.2 Replace `any([n is not None for n in tasks])` with a live count of
      non-`None` slots, decremented at the `StopAsyncIteration` branch.
- [x] 2.3 Add a `{task: index}` dict maintained alongside `tasks` and replace
      `tasks.index(task)` with a lookup; keep it in sync at all three mutation
      points (initial fill, replacement after a yielded result, `None` on
      exhaustion), and make sure the `finally` cancel-and-gather is untouched.
- [x] 2.4 Re-measure against 2.1 and record the figures in the change (in
      `proposal.md` or a note under **Done** at archive time). Gate: must not
      regress. "No measurable difference, taken for clarity" is an acceptable
      recorded outcome.
- [x] 2.5 Full suite green with no test file edited; lint, format and `ty`.

## 3. Private accumulator types out of public signatures (part e)

- [x] 3.1 Widen the `A` parameter to `Any` in the return annotation of every
      public collector factory in `collector.py`: `counting`, `summing_int`,
      `summing_long`, `summing_double`, `averaging_int`, `averaging_long`,
      `averaging_double`, `summarizing_int`, `summarizing_long`,
      `summarizing_double`, `min_by`, `max_by`, `reducing` (all overloads and
      the implementation signature), `to_map`, `grouping_by`,
      `partitioning_by`, `mapping`, `collecting_and_then`.
- [x] 3.2 Leave the private helpers (`_summing`, `_averaging`, `_summarizing`,
      `_extremum`, `_reducing` if present) pinned to their precise box types,
      and leave every box class itself unchanged.
- [x] 3.3 Grep the public surface for any remaining private type name reachable
      from a public signature; `ty check src` must pass, and the full suite must
      be green with no test file edited.

## 4. `to_list` becomes a factory (part a) — BREAKING

- [x] 4.1 In `collector.py`, turn `to_list` into
      `def to_list() -> Collector[T, list[T], list[T]]` returning
      `Collector(list, list.append)`. Replace the "bare instance, not a factory"
      comment with the reasoning that now applies.
- [x] 4.2 Update the internal call sites: `grouping_by` and `partitioning_by`'s
      `downstream` default to `to_list()` (evaluated once at definition time,
      per design.md), and `stream.py`'s `to_array()` to `collect(to_list())`.
- [x] 4.3 Update every `collect(to_list)` in `tests/` to `collect(to_list())`,
      plus any explicit `to_list` passed as a `downstream`. This is the only
      permitted test edit in the whole change — verify by diff that nothing else
      in `tests/` changed.
- [x] 4.4 Add tests for the new shape: `collect(to_list())` returns the list;
      passing the bare `to_list` function raises `StreamBuildException` naming
      `Collector` and leaves the stream unconsumed; one value returned by a
      single `to_list()` call feeds two separate collections with independent
      results; the `grouping_by`/`partitioning_by` 1-arg default still builds
      lists.
- [x] 4.5 Update `README.md`: the `to_list` API-table row (kind column
      `instance` -> `factory`), every example using `collect(to_list)`, the
      `grouping_by`/`partitioning_by` signature rows showing
      `downstream: Collector = to_list`, and the `collect()` migration entry's
      list of collectors if it names `to_list` in the bare form.
- [x] 4.6 Add a new `0.3.5 -> next` migration-log entry in `README.md`: what
      changed, why (one factory rule, Java's `Collectors.toList()`), the exact
      call-site edit, and that it breaks loudly with `StreamBuildException`.
- [x] 4.7 Update `CLAUDE.md`'s collectors paragraph, which names `to_list` as a
      collector alongside `to_generator`.
- [x] 4.8 Grep the whole repo (excluding `openspec/changes/archive/` and the
      roadmap's **Done** section, which are history) for a remaining bare
      `collect(to_list)`.

## 5. Verification and close-out

- [x] 5.1 Full suite green: `uv run pytest`, then
      `uv run pytest --cov-fail-under=98`.
- [x] 5.2 `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run ty check src`.
- [x] 5.3 `openspec validate --change batch-small-cleanups --strict`.
- [x] 5.4 Move the **Now** item to **Done** in `roadmap.md` with the outcome of
      each part, including 2.4's measured figures, and leave **Now** empty (or
      note what, if anything, promotes up from **Later**).
