<!-- design.md deliberately skipped: its instruction is conditional ("create
only if any apply") and none of the four criteria do. Two modules are touched
but no architectural pattern is introduced; there is no new dependency, data
model, security, performance or migration concern; and the one ambiguity —
`Collector.demand()` against a free `demand_of()` in `ordering.py` — is
resolved and recorded in proposal.md under "The one judgment call". -->

## 1. Move the derivation onto the collector

- [x] 1.1 Add `from snakestream.ordering import OrderDemand` to `collector.py`
      and verify `uv run ty check src` still passes and no import cycle is
      introduced (`ordering.py` imports only `enum` at runtime, so the new
      `collector -> ordering` edge must stay acyclic).
- [x] 1.2 Add `Collector.demand()` returning `OrderDemand.NONE` where
      `Characteristics.UNORDERED` is in `self.characteristics` and
      `OrderDemand.IF_ORDERED` otherwise. Docstring states the rule
      `collector-protocol` L105 requires and names `collect()` as its caller.
      Verify by unit test: a `Collector` declaring `UNORDERED` reports `NONE`,
      one declaring nothing reports `IF_ORDERED`.
- [x] 1.3 Confirm `demand()` is bare-named per `internal-name-visibility` (it
      is reachable by a caller constructing a `Collector` directly, which is a
      supported shape) and verify `uv run pytest tests/test_name_visibility.py`
      passes.

## 2. Route the three call sites through it

- [x] 2.1 Replace the inline conditional at `stream.py:488` (`collect()`,
      1-arg branch) with `collector.demand()`. Verify
      `uv run pytest tests/test_collect.py tests/test_collector.py` passes.
- [x] 2.2 In `collect()`'s 3-arg branch, call `demand()` on the `Collector` it
      already builds and **delete** the comment re-deriving `IF_ORDERED`; with
      no characteristics declared the value now follows by construction.
      Verify `uv run pytest tests/test_collect.py` passes — the 3-arg form's
      cases are at lines 127-150 there.
- [x] 2.3 Trim `to_array()`'s comment at `stream.py:553` — the derivation
      behind it is now one hop. Verify `uv run pytest tests/test_to_array.py`
      passes.

## 3. Confirm behaviour is unchanged

- [x] 3.1 Run the barrier scenarios that are this change's real regression
      test — `uv run pytest tests/test_racing_encounter_order.py
      tests/test_racing_delivery_order.py tests/test_collector.py
      tests/test_collect.py` — and verify the UNORDERED-takes-the-order-blind-path
      and delivery-barrier-engaged cases still pass unmodified. No test should
      need editing; if one does, the change is not behaviour-preserving and the
      proposal's `skip_specs: true` premise is wrong.
- [x] 3.2 Run the full gate as CI does: `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src`,
      and `uv run pytest --cov-fail-under=98`. Verify all pass.
- [x] 3.3 Verify no per-element cost was introduced by inspection rather than
      measurement: `demand()` is called once per `collect()`, never inside a
      sink's `accept()`. Confirm no call site sits on a per-element path.

## 4. Record

- [x] 4.1 Confirm no README Migration entry is owed — no public API changes
      and no behaviour changes, so the migration-log rule does not fire.
      Verify by re-reading the diff for any change to an exported name.
- [x] 4.2 Run `openspec validate "derive-order-demand-on-the-collector"` and
      verify it still reports valid, then archive per the usual cycle.
