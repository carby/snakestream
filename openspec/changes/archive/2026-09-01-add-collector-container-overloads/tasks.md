## 1. The shared finisher

- [x] 1.1 In `src/snakestream/collectors.py`, change `_finish_groups()` to write
  each finished value back into `groups` and return that same mapping, instead
  of building a new `dict` in either path. Iterate `list(groups)` rather than
  the mapping itself. Verify `uv run pytest tests/test_grouping_by.py
  tests/test_partitioning_by.py` still passes with no test edits — the change is
  specified to be unobservable for both.
- [x] 1.2 Add the comment recording why: the caller's mapping type has to
  survive the finisher, which a rebuild into `dict` destroys; and that the
  no-finisher path's former `dict(groups)` copy was referenced by nothing, so
  dropping it costs no isolation. Name `list(groups)` as being for an arbitrary
  `MutableMapping` rather than for `dict`, which cannot resize on a rebind.

## 2. `to_map`'s container argument

- [x] 2.1 Add a mapping typevar bound to `MutableMapping` to
  `src/snakestream/type.py`, beside `_C`, with a one-line comment saying why
  `_C` (bound to `_SupportsAdd`) does not serve. Verify `uv run ty check src`
  is clean.
- [x] 2.2 Give `_ToMapBox.result` no default and have `to_map`'s `_supply`
  become `async def`, building the box from `await _maybe_await(map_supplier)`
  with `dict` as the default. Verify the existing `tests/test_to_map.py` passes
  unchanged.
- [x] 2.3 Add the three-entry `@overload` block above `to_map` — `(k, v)`,
  `(k, v, merge)`, `(k, v, merge, map_supplier)` — each carrying
  `# pragma: no cover`, following `reducing()`'s block directly above. Leave the
  implementation signature positional; `to_map`'s argument positions do not
  shift, so no arity branch is needed.
- [x] 2.4 Extend the comment on `to_map`'s `Collector(...)` call to say that the
  4-arg form declares nothing on the merge's account alone, so a caller-supplied
  container never reaches the characteristics decision here — the one place a
  reader is likely to look for the container rule and not find it.

## 3. Tests for `to_map`

- [x] 3.1 In `tests/test_to_map.py`, assert the 4-arg form returns the caller's
  type: collect into `OrderedDict` and assert both `isinstance(result,
  OrderedDict)` and the expected pairs.
- [x] 3.2 Add tests for a fresh mapping per collection (same collector instance
  used twice), for the empty stream yielding an empty `OrderedDict`, and for a
  duplicate key merging into the caller's mapping.
- [x] 3.3 Add a test that an async `map_supplier` is awaited, following the
  file's existing async-mapper tests.
- [x] 3.4 Assert `Characteristics.UNORDERED not in to_map(k, v, merge,
  OrderedDict).characteristics`, and that `to_map(k, v)` still declares it.
- [x] 3.5 Add `tests/typing/bad_to_map_container_without_merge.py` calling
  `to_map(k, v, map_supplier=dict)`, and a `tests/test_static_typing.py` case
  asserting `ty` rejects it. This is the only thing that enforces "no
  `to_map(k, v, map_supplier)` form" — there is deliberately no runtime raise.

## 4. `grouping_by`'s container argument

- [x] 4.1 Add the three-entry `@overload` block above `grouping_by` —
  `(classifier)`, `(classifier, downstream)`, `(classifier, map_factory,
  downstream)` — each with `# pragma: no cover`.
- [x] 4.2 Change the implementation signature to `_UNSET` defaults and add the
  arity branch that shifts the positionals when only two arrive, mirroring
  `reducing()`'s branch and its comment shape. Verify every existing
  `tests/test_grouping_by.py` case passes untouched — the two-argument call
  binding its `Collector` to `downstream` is the whole point.
- [x] 4.3 Make `_supply` `async def`, seeding `_GroupBox` from `await
  _maybe_await(map_factory)` with `dict` as the default. Keep
  `_check_downstream(downstream)` running on the resolved argument, after the
  arity branch, so the 3-arg form rejects a non-`Collector` downstream too.
- [x] 4.4 Pass `characteristics=()` when a `map_factory` was supplied and
  `downstream.characteristics` otherwise, and extend the existing derivation
  comment with the bound: it rests on `dict` equality ignoring key insertion
  order, `OrderedDict`'s does not, and the exclusion keys on the factory being
  supplied rather than on the type it produces — with the reason
  (`map_factory is dict` is a whitelist, and calling the factory early to
  inspect it is not allowed). Point at `to_collection()` as the same rule.

## 5. Tests for `grouping_by`

- [x] 5.1 In `tests/test_grouping_by.py`, assert the 3-arg form returns the
  caller's type, that a downstream finisher's results land in it, that each
  collection gets a fresh mapping, that the empty stream yields an empty one,
  and that an async `map_factory` is awaited.
- [x] 5.2 Assert a non-`Collector` third argument raises `StreamBuildException`,
  matching the 2-arg form's existing case.
- [x] 5.3 Add the arity-dispatch tests: `grouping_by(f, counting())` still
  yields a plain `dict`, and `grouping_by(f)` still yields
  `dict[K, list[T]]` — the regression pair for decision 1.
- [x] 5.4 Assert `UNORDERED` is absent from `grouping_by(len, OrderedDict,
  to_set()).characteristics` **and** from `grouping_by(len, dict,
  to_set()).characteristics`, the second pinning that the exclusion follows from
  the factory being supplied rather than from the type.
- [x] 5.5 In `tests/test_racing_delivery_order.py`, add the observation test
  that `grouping_by(f, OrderedDict, to_set())` under an ordered racing pipeline
  takes the barrier — key insertion order follows encounter order — following
  `test_grouping_by_into_an_unordered_downstream_skips_the_barrier`'s shape as
  its mirror.

## 6. Docs and gates

- [x] 6.1 In `README.md`, flip the `to_map(key_mapper, value_mapper,
  merge_function, map_supplier)` and `grouping_by(classifier, map_factory,
  downstream)` rows to `x` and rewrite their cells: what the argument does, that
  the result is the caller's type returned as-is, that `grouping_by`'s form is
  selected by arity so existing calls are unaffected, and that a caller-supplied
  container declares no `UNORDERED` with `unordered()` as the lever. State on
  the `to_map` row that there is no `(k, v, map_supplier)` form and why. **No
  Migration entry** — nothing breaks.
- [x] 6.2 In `roadmap.md`, close gaps 2 and 3 under **Now** -> **Queued
  changes**, retiring their numbers as that section's convention requires and
  updating its "Four remain" count and the surrounding prose to match. Leave
  gaps 4 and 5.
- [x] 6.3 Run the full CI-equivalent gate: `uv run ruff check .`, `uv run ruff
  format --check .`, `uv run pytest`, `uv run ty check src`, and `uv run pytest
  --cov-fail-under=98`.
