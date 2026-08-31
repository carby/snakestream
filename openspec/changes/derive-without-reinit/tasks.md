## 1. Turn the existing test into a reproduction

- [x] 1.1 Tighten `test_a_user_subclass_survives_a_mode_switch` in `tests/test_execution_model.py` from `seq.resource == "db-handle"` to an identity assertion against an object assigned in `__init__`, and confirm it now **fails** on `main` — the change is not guarded until this test can fail.
- [x] 1.2 Add a test counting subclass `__init__` invocations across three intermediate ops plus one mode switch, asserting exactly one; confirm it fails, reporting five.
- [x] 1.3 Add a test for the acquire-in-`__init__` / release-in-overridden-`close()` shape, asserting one acquisition and one release; confirm it fails, reporting three acquisitions and one release.

## 2. Change the derivation mechanism

- [x] 2.1 Replace `type(self)(self._source, self._close_handlers)` in `Stream._derive()` with `copy.copy(self)`, keeping the subsequent `_chain` and `_executor` assignments and the `self._consumed = True` ordering unchanged.
- [x] 2.2 Update `_derive()`'s docstring: it currently explains the no-op chain-by-identity optimisation and the consumed-on-the-way-out rule, and must now also carry why derivation copies rather than constructs, and that a subclass's `__copy__` is honoured.
- [x] 2.3 Confirm the three tests from group 1 pass, and that the full suite passes unchanged.

## 3. Cover the widened constructor contract

- [x] 3.1 Test a subclass with `__init__(self, dsn)` that calls `super().__init__()` with a source of its own: intermediate ops and a mode switch succeed and return instances of that subclass. Confirm it raises `TypeError` before the change.
- [x] 3.2 Test a subclass with `__init__(self)` taking no arguments at all, through an intermediate op and a mode switch.
- [x] 3.3 Test that subclass state is shared by reference: mutating a mutable attribute through a derived stage is visible through the original reference.
- [x] 3.4 Test that `Stream` itself defines no `__copy__`, and that a subclass's `__copy__` runs on derivation.

## 4. Documentation

- [x] 4.1 Update CLAUDE.md's AutoClose section to state that a subclass constructor runs once per pipeline and may take any signature — the two facts that make the documented resource-wrapping use case writable.
- [x] 4.2 Check whether README documents subclassing; if so, align it, and if not, leave it alone rather than opening a new section.

## 5. Validation

- [x] 5.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [x] 5.2 `uv run pytest --cov-fail-under=98`.
- [x] 5.3 `openspec validate derive-without-reinit`.
