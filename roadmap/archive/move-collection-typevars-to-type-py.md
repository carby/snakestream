+++
id = "move-collection-typevars-to-type-py"
title = "Moved `to_collection()`'s private `_C` TypeVar and `_SupportsAdd` to `type.py`"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Moved `to_collection()`'s private `_C` TypeVar and `_SupportsAdd`
protocol from `collector.py` to `type.py`** (2026-08-24). The last public
collector signature naming a type outside `type.py`, the project's
established home for shared callable/composite type aliases —
`to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C,
_C]` kept `_C`/`_SupportsAdd` defined locally instead. Deliberately left
alone on 2026-08-21 when the other 18 collector factories widened their
accumulator parameter to `Any`, because here `A` genuinely is the caller's
own container type rather than an internal box, so `_C` had to move rather
than be erased.

Pure relocation, both names moved together as a pair since `_C`'s bound is
`_SupportsAdd`: `to_collection`'s signature and behavior are unchanged, and
both stay private (leading underscore) and unexported — a caller never
writes `_C` themselves, the checker infers it. Full suite green (535
tests) with **no test file edited**, `ruff`, `ty check src` and `openspec
validate --strict` all pass. `skip_specs: true`: no spec-level behavior
changed, only where two private type declarations live. See
`openspec/changes/archive/2026-08-24-move-to-collection-typevar-to-type-module`.
