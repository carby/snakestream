## 1. Restructure the `Op` hierarchy in `sink.py`

- [x] 1.1 Add a new `Op` subclass (e.g. `_ArgsOp`) holding the
      `__init__(self, *args: Any) -> None` body and the
      `_sink_cls: ClassVar[Callable[..., Sink[Any]]]` declaration currently
      duplicated between `StatelessOp` and `StatefulOp`.
- [x] 1.2 Make `StatelessOp(_ArgsOp)` keep only its existing `link()`
      (`return self._sink_cls(downstream, *self._args)`) and its own
      docstring.
- [x] 1.3 Make `StatefulOp(_ArgsOp)` — no longer subclassing `StatelessOp` —
      keep only its existing `link()`
      (`return self._sink_cls(downstream, self, *self._args)`).
- [x] 1.4 Rewrite `StatefulOp`'s docstring to drop the disclaimer paragraph
      ("Subclassing `StatelessOp` is a mechanical convenience... does not
      mean a stateful op is a kind of stateless one") since it no longer
      subclasses `StatelessOp`; keep the parts describing what shared state
      is and how a subclass declares it.

## 2. Verify no behaviour or public-surface change

- [x] 2.1 Confirm `StatelessOp` and `StatefulOp` are still both importable
      from `snakestream.sink` with unchanged constructor signatures
      (`__init__(self, *args)`).
- [x] 2.2 Run `uv run pytest` and confirm the full suite passes with **no
      test file edited** (grep-diff `tests/` before/after).
- [x] 2.3 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 2.4 Run `uv run ty check src`.
- [x] 2.5 Confirm `openspec validate --strict` passes given `skip_specs:
      true`.

## 3. Close out

- [x] 3.1 Update roadmap.md: move item 1 of the **Now** table to **Done**
      with a summary of what landed (mirroring the style of prior **Done**
      entries), and renumber the remaining **Now** items (2-4 -> 1-3).
- [ ] 3.2 Archive the change per the project's `opsx:archive` workflow.
