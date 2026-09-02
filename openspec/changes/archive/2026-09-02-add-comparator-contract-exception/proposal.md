## Why

`exception-hierarchy` exists so "a caller can catch anything snakestream raised
without enumerating the leaves". One raise escapes it: a comparator returning a
non-`int` raises a bare `TypeError`, from six sites across `sort.py` and
`comparator.py`. It is the only exception this library raises that no
`except StreamException` catches, so an application that wants to separate
"snakestream rejected something the caller supplied" from genuine runtime
failure cannot: the bad-comparator case sails past the library-scoped handler
into the generic one.

The asymmetry is sharpest inside a single function. `sort.py`'s
`_checked_segment_comparator` raises `StreamBuildException` for an async
comparator segment two lines above raising a bare `TypeError` for a non-`int`
result — the same class of fault, "the comparator you supplied does not meet
its contract", one inside the hierarchy and one outside.

## What Changes

- Add `ComparatorContractException(StreamBuildException, TypeError)` to
  `snakestream.exception`. It takes the offending value and owns its own
  wording, so the message stays a module-private constant rather than a second
  exported name. MRO is verified valid and linearizes as
  `ComparatorContractException -> StreamBuildException -> StreamException ->
  TypeError -> Exception`.
- Raise it in place of the bare `TypeError` at all six check sites: three in
  `sort.py` (`_checked`, `_checked_segment_comparator`, `_merge`) and three in
  `comparator.py` (`is_new_extremum`, `_comparator_segment_sign_sync`,
  `_comparator_segment_sign_async`).
- Retire the public `COMPARATOR_RESULT_TYPE_MESSAGE` introduced by the
  preceding commit. With a class to hang the wording on there is no reason to
  export the message separately, and its comment was wrong on two counts: it
  claimed seven check sites (six — it counted the deleted
  `check_comparator_result_type` definition) and opened "the one TypeError this
  library raises rather than defining", which this change makes false.
- Not breaking. `except TypeError` still catches it — which
  `comparator-contract` requires and eight existing tests assert — and
  `except StreamBuildException` / `except StreamException` now catch it too.
  Purely widening, so no call site can stop catching what it caught before.
- README gains a Migration entry marked `(not breaking)`, following the
  precedent of the `StreamException` base entry.

## Capabilities

### New Capabilities

None. This adds a leaf to an existing hierarchy and changes which exception
type an already-specified raise uses; both are requirement changes to specs
that already exist.

### Modified Capabilities

- `exception-hierarchy`: its requirement enumerates the leaves by name ("As of
  this change those are `StreamBuildException` and `IllegalStateException`") and
  must name the third. It also states the base "SHALL NOT derive from any
  built-in exception other than `Exception`" — that constraint binds the base,
  and the spec must say explicitly that a *leaf* may mix in a built-in where
  the fault genuinely is one, so the new leaf is not read as violating it.
- `comparator-contract`: its "Comparators must not return bool" requirement says
  `sorted()`, `min()` and `max()` SHALL raise `TypeError`. That stays true and
  stays the guarantee callers may rely on; the spec must record that the raised
  type is now a subclass, and that the subclass — not bare `TypeError` — is what
  is raised.

## Impact

- `src/snakestream/exception.py` — one new class, and a correction to the
  message constant's comment.
- `src/snakestream/sort.py`, `src/snakestream/comparator.py` — six raise
  sites change the exception type; no control flow, message, or condition
  changes.
- `README.md` — Migration log entry.
- Tests: the eight existing `pytest.raises(TypeError)` assertions keep passing
  unchanged, which is the compatibility evidence; new tests assert the three
  additional catches and the MRO.
- No public API is renamed or removed, and nothing outside
  `snakestream.exception` is exported.
