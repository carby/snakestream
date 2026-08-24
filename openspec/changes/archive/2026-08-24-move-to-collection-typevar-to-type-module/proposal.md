## Why

`to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C, _C]`
(`collector.py:655-669`) is the one public collector signature still naming a
private type: `_C` and its bound, `_SupportsAdd`, are defined locally in
`collector.py` rather than in `type.py`, where the project's convention puts
every other shared callable/composite type alias. Every other collector
factory had its accumulator parameter widened to `Any` on 2026-08-21
specifically because `A` there is an internal box; `to_collection` was left
alone because here `A` genuinely is the caller's own container type. That
correct decision left `_C`/`_SupportsAdd` stranded outside the module where
the project keeps this kind of type.

## What Changes

- Move `_SupportsAdd` (the `Protocol` requiring an `add()` method) and `_C`
  (the `TypeVar` bound to it) from `collector.py` to `type.py`, alongside the
  project's other functional-interface-style aliases.
- `collector.py` imports both from `type.py` instead of defining them.
- No signature, behavior, or runtime type changes: `to_collection`'s
  parameter and return types stay exactly as they read today. This is a
  pure relocation of two private type declarations.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — no spec-level behavior changes; this moves private type-checking
declarations only, resolved via `skip_specs: true`)

## Impact

- `src/snakestream/type.py`: gains `_SupportsAdd` and `_C`.
- `src/snakestream/collector.py`: `to_collection`'s two supporting
  declarations are removed in favor of an import; the function body and
  signature are untouched.
- No public API change, no README update, no test behavior change. `ty check
  src` must still pass with `_C`'s bound resolving correctly from its new
  location.
