## 1. Move the type declarations

- [x] 1.1 In `src/snakestream/type.py`, add `from typing import Protocol` to
      the existing `typing` import, then add `_SupportsAdd` (the `Protocol`
      with an `add(self, item: Any) -> Any` method) and `_C = TypeVar("_C",
      bound=_SupportsAdd)`, matching their current definitions in
      `collector.py` verbatim.
- [x] 1.2 In `src/snakestream/collector.py`, delete the `_SupportsAdd` class
      and `_C` TypeVar definitions (`collector.py:655-659`), and import both
      from `type.py` instead, alongside the module's existing `type.py`
      imports.
- [x] 1.3 Confirm `to_collection`'s signature is byte-identical to before:
      `def to_collection(collection_supplier: Supplier[_C]) -> Collector[Any,
      _C, _C]:`.

## 2. Verify

- [x] 2.1 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 2.2 Run `uv run ty check src` and confirm `_C`'s bound resolves
      correctly from its new location (no new type errors).
- [x] 2.3 Run `uv run pytest` and confirm the full suite passes with **no
      test file edited** — this is a pure relocation of private type
      declarations, so nothing observable changes.
- [x] 2.4 Run `openspec validate --strict` to confirm the `skip_specs: true`
      change validates cleanly with no spec deltas.
