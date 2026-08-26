## 1. Remove the dead cast (independent, lands first)

- [ ] 1.1 In `stream.py`, replace `_derive_executor()`'s body
  `return cast("Stream[T]", self._derive(self._chain, executor))` with
  `return self._derive(self._chain, executor)`.
- [ ] 1.2 Confirm the `cast` import is still used — `iterate()` and the 3-arg
  `collect()` — and leave it in place.
- [ ] 1.3 Run `uv run ty check src`. It must pass; `cast` is erased at runtime,
  so no test can distinguish the two forms and `ty` is the only gate.
- [ ] 1.4 Run `uv run pytest` and `uv run ruff check . && uv run ruff format --check .`.
  Commit this on its own — it is correct independently of everything below.

## 2. Collapse the three methods into one

- [ ] 2.1 Change `_derive`'s signature to `def _derive(self, op: Op | None = None) -> Stream[Any]`
  and set `new_stream._chain = [*self._chain, op] if op is not None else self._chain`
  (`is not None`, not `if op` — design.md Decision 1). Keep `new_stream._executor
  = self._executor`, and keep `_check_not_consumed()` before the copy with
  `self._consumed = True` after it.
- [ ] 2.2 Move `_extend`'s docstring intent onto `_derive`: the chain-extension
  rule now lives in this body and nowhere else.
- [ ] 2.3 Delete `_extend()` and rewrite its nine call sites as
  `self._derive(<Op>)` — `filter`, `map`, `flat_map`, `sorted`, `distinct`,
  `peek`, `limit`, `skip`, `unordered`. Each stays a one-liner.
- [ ] 2.4 Delete `_derive_executor()` and rewrite `sequential()` / `parallel()`
  as derive-then-assign: `derived = self._derive()`, `derived._executor =
  SEQUENTIAL` / `RACING`, `return derived`.
- [ ] 2.5 `grep -n "_extend\|_derive_executor" src/` returns nothing.

## 3. Re-site the immutability warning

- [ ] 3.1 Put the full "must not assign onto self and return self" paragraph on
  `sequential()`, since the new body is a one-line edit away from the forbidden
  in-place flip (design.md Decision 4).
- [ ] 3.2 Keep the "must not compose" warning in shortened form — the body now
  shows it — and keep the note that the chain carrying over unchanged is what
  carries the ordering characteristic, which `_is_ordered()` folds from there.
- [ ] 3.3 Make `parallel()`'s docstring point at `sequential()` rather than
  restating either paragraph. A verbatim duplicate across the two is the
  specific failure this change exists not to repeat.

## 4. Verify nothing observable moved

- [ ] 4.1 `uv run pytest` green with **no test file edited**: `git diff -- tests/`
  must be empty. This is the tripwire, not a formality — the existing
  `pipeline-immutability`, `pipeline-composition` and `stream-execution-model`
  tests already pin every contract touched.
- [ ] 4.2 Confirm specifically that the position-independence tests for
  `.parallel()`/`.sequential()` and the "queued chain survives a mode switch"
  scenario still pass, and that reuse of an extended reference still raises
  `IllegalStateException` for both an intermediate op and a mode switch.
- [ ] 4.3 `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run ty check src`, `uv run pytest --cov-fail-under=98`.
- [ ] 4.4 `openspec validate collapse-derive-wrappers --strict`.
- [ ] 4.5 No benchmark run needed, and say so in the commit message: this is
  chain-building and mode-switch code, executed once per composition, with
  nothing added to any `accept()` body or per-element path.

## 5. Correct the prose that named the deleted methods

- [ ] 5.1 `CLAUDE.md:61` — rewrite the `.parallel()`/`.sequential()` sentence so
  it no longer says they "go through `_derive_executor()`". Check line 34's
  `_derive()` reference still reads true against the new signature.
- [ ] 5.2 `roadmap.md:1195` (2026-08-24 **Done**) — annotate the sentence "so it
  is `_derive_executor()`, never `self._executor = X; return self`" to record
  that the method is gone and where the rule now lives. Do not rewrite history
  to pretend the shape never existed.
- [ ] 5.3 `roadmap.md:727-745` (2026-08-25 **Done**, finding (a)) — annotate the
  `_extend` description the same way, including that its ergonomic win survives
  in `_derive(op)`.
- [ ] 5.4 `grep -rn "_derive_executor\|_extend" --include=*.md .` — every
  surviving hit is either an annotated history entry or an archived change under
  `openspec/changes/archive/` (archived changes are records and are left alone).
- [ ] 5.5 Add the **Done** entry when archiving, and make it state explicitly
  what was different from the 2026-08-24 merge — otherwise the next reader has a
  Done entry describing a shape that no longer exists, which is exactly how
  `_derive_executor()` came back the first time.
