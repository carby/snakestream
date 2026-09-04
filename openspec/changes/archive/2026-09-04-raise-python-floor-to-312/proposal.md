## Why

Second of four sequenced floor raises heading to 3.14-only; see
`openspec/changes/archive/2026-09-04-raise-python-floor-to-311` for the first
and for the destination (free-threading, PEP 779, as the substrate for a
contiguous-splitting `spliterator()`).

This step drops 3.11 and takes **PEP 695**, the typing-syntax change 3.12
brought. The payoff is concentrated rather than cosmetic: the package's central
vocabulary — `type.py`'s ~20 functional-interface aliases — is currently built
out of module-level `TypeVar`s that eight of the ten modules import, and one of
those aliases carries a quoted forward reference (`FlatMapper`) purely because
`Stream` is a `TYPE_CHECKING`-only import. A PEP 695 `type` statement's
right-hand side is **lazily evaluated**, so the quotes come off two steps ahead
of PEP 649.

## What Changes

- **BREAKING**: `requires-python` moves from `>=3.11` to `>=3.12`. Installing on
  3.11 now fails at resolution.
- **BREAKING** (runtime introspection, silent): `type.py`'s aliases become
  `TypeAliasType` objects rather than subscripted generic aliases. Verified:
  `get_args(Mapper[int, str])` changes from `([int], str | Awaitable[str])` —
  the substituted structure — to `(int, str)` — the type arguments; `get_origin`
  changes from `collections.abc.Callable` to the alias itself; the right-hand
  side is reachable only via `.__value__`. Static typing is unaffected, which is
  the surface anyone actually uses these for.
- The four generic classes take PEP 695 parameter lists — `Stream`,
  `StreamBuilder`, `Sink`, `Collector` — which is ruff's `UP046` at `py312` and
  the only lint finding this bump produces.
- `type.py`'s aliases become `type X[T, R] = ...` statements. `FlatMapper`'s
  `"Stream[R]"` is unquoted, since the RHS is lazy.
- **`Aiter`, `C` and `M` deliberately stay `TypeVar`s**, as do `T`, `R` and `A`.
  They are shared across modules (and `C`/`M` are *bound*: `_SupportsAdd` at 3
  sites, `MutableMapping[Any, Any]` at 5), and PEP 695 has no syntax for a
  shared, named, bound type variable. Inlining them would repeat each bound at
  every use site and delete a shared vocabulary CLAUDE.md's naming rule
  explicitly endorses. See `design.md`, decision 2.
- The 3.11 leg is removed from both CI matrices; `ruff`'s `target-version`
  moves to `py312`.
- Docs and specs stating the matrix are corrected; a README Migration entry
  records both breaks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-smoke-test`: the stated matrix moves from 3.11–3.14 to 3.12–3.14.

**Deliberately not modified — `generic-stream-typing`.** Every requirement
there is stated as observable typing behaviour (`ty` infers `Stream[str]`,
`Mapper[T, R]`'s declared return type is exactly `R | Awaitable[R]`) and none
names `Generic`, `TypeVar` or any other mechanism. PEP 695 is a change of
spelling that leaves all of it true, so there is no delta to write — the spec
passing unchanged is the evidence the conversion is faithful, and it is checked
by `tests/typing/` rather than asserted. See `design.md`, decision 3.

## Impact

- `pyproject.toml` — `requires-python`, `[tool.ruff] target-version`
- `.github/workflows/check.yml` — both matrices
- `src/snakestream/type.py` — ~20 aliases to `type` statements; `TypeVar` import
  retained for the six that stay
- `src/snakestream/stream.py`, `stream_builder.py`, `sink.py`, `collector.py` —
  class parameter lists; `Generic` import drops from each
- `CLAUDE.md`, `README.md`, `openspec/specs/install-smoke-test/spec.md`
- No public API surface added or removed; no behaviour change on any supported
  interpreter beyond the introspection break noted above.
