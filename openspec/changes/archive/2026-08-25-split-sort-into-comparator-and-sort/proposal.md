## Why

`sort.py` is named for one of the three things it holds. `check_comparator_result_type`
and `is_new_extremum` are comparator *semantics* — the int contract and the
first-of-tied-wins rule — and their consumers are `terminals.py` (`_MinMaxSink`)
and `collector.py` (`min_by`/`max_by`), neither of which sorts anything. Both
therefore import from a module named `sort` to get something that has nothing to
do with sorting, which is the concrete defect: the module name misdirects every
reader who follows those imports.

Story 4 (`sort-with-cmp-to-key`, landed 2026-08-25) added a third thing — the
`sort()` dispatcher and its `_checked()` wrapper — and left the module mostly
unannotated while `ty` gates the 3.14 leg in CI. Story 5 of the 2026-08-25 batch
is the last unblocked item in **Now** with nothing waiting on it.

## What Changes

- **New `src/snakestream/comparator.py`** holding the comparator semantics:
  `check_comparator_result_type` and `is_new_extremum`, moved verbatim. It matches
  the `comparator-contract` spec that already governs both.
- **`src/snakestream/sort.py` keeps sorting**: `sort()`, `_checked()`, `merge_sort()`
  and `_merge()`, importing the two semantics functions from `comparator.py`.
  `sort()` — the seam between the two concerns — lands here, on the side that calls
  the semantics rather than the side that defines them; `ops.py` remains its only
  external caller.
- **Imports updated at three call sites**: `terminals.py` and `collector.py` import
  `is_new_extremum` from `comparator.py` and no longer reference `sort` at all;
  `ops.py`'s `sort` import is unchanged.
- **Annotations completed** on `merge_sort` and `_merge`, the two functions story 4
  left bare, so no module in `src/` is unannotated. This was not settled with the
  user before writing; it is assumed in scope because the roadmap row names it and
  the file is already open for the move. It is confined to task group 4 and can be
  dropped without affecting the rest.
- No public API change, no behaviour change: every moved function keeps its name,
  signature and body. `snakestream.sort` and `snakestream.comparator` are both
  private modules — neither is re-exported from `__init__.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This change sets `skip_specs: true`: it moves private functions between
private modules without altering a single observable behaviour. The int contract,
the bool rejection, the first-of-tied-wins tie-break, sort stability, `reverse`
handling and async-comparator support are all governed by `comparator-contract`
and all unchanged — the functions implementing them are moved byte-for-byte.
`static-type-checking` requires only that `ty` passes over `src/snakestream`,
which the annotation work strengthens without changing the requirement.

## Impact

- `src/snakestream/comparator.py` — **new**, ~35 lines.
- `src/snakestream/sort.py` — loses the two semantics functions, gains an import
  from `comparator.py`, gains annotations on `merge_sort`/`_merge`.
- `src/snakestream/terminals.py:9` and `src/snakestream/collector.py:11` — import
  line retargeted from `snakestream.sort` to `snakestream.comparator`.
- `src/snakestream/ops.py:15` — unchanged (`from snakestream.sort import sort`).
- `src/snakestream/type.py` — **one added alias**, `AsyncComparator`, beside
  `Comparator`. Not in the original scope: annotating `merge_sort`/`_merge` with the
  `Comparator` union turns their unconditional `await` into a `ty` error, so the
  narrowed arm has to exist. Amended during apply, user-approved — see design.md —
  Decision 4.
- **No test change.** Verified 2026-08-25 at `0312a67`: zero references to
  `snakestream.sort`, `merge_sort`, `is_new_extremum` or `check_comparator_result_type`
  anywhere outside `src/` — not in `tests/`, `README.md` or `openspec/specs/`.
  The only other hits are historical prose in `roadmap.md` and archived changes,
  which describe the past and are not updated. A test edit in this change is the
  story's tripwire.
- `README.md` — no change; the module layout is not documented there.
- `roadmap.md` — story 5 moves from **Now** to **Done**.
