## 1. Sweep the mechanical call sites, before the semantics flip

Ordering note: `Stream.of(X)` and `Stream(X)` are the *same call* until task 3.1
lands (design.md, Decision 2), so this whole group is behaviour-preserving under
today's semantics. Doing it first keeps the suite green on both sides of the flip
and isolates any breakage to the three lines in group 3.

- [x] 1.1 Write the sweep script under the scratchpad (not committed): rewrite single-argument `Stream.of(X)` -> `Stream(X)`, leaving zero- and multi-argument calls alone. Verify it reports 1,084 candidate sites and that every one is single-line.
- [x] 1.2 Add the denylist from design.md Decision 4 — `roadmap/decisions.md`, `README.md` below the `## Migration` heading, `openspec/changes/archive/**` — plus the 22 scalar-set sites from Decision 3. Verify the script now reports those paths as skipped and names the scalar sites individually.
- [x] 1.3 Run the sweep over `tests/**` only. Verify `uv run pytest` is green with no source change yet — this is the proof that the substitution is behaviour-preserving.
- [x] 1.4 Run the sweep over the 24 live specs under `openspec/specs/**` excluding `stream-construction`. Verify no normative text changed (`git diff` shows only lines inside `#### Scenario:` blocks and prose examples) and `uv run pytest tests/test_roadmap.py` still passes.

## 2. Split `tests/test_of.py`

- [x] 2.1 Move the five normalization tests (`test_input_list`, `test_input_async_generator`, `test_input_async_iterator`, `test_single_generator_input`, `test_single_empty_list`) onto `Stream(...)`. Verify they pass unchanged in substance.
- [x] 2.2 Move the nine scalar-set tests (`test_null_input`, `test_single_var_input`, `test_single_empty_dict`, `test_single_str_input`, `test_single_bytes_input`, `test_single_populated_dict`, `test_single_bytearray_input`, `test_single_memoryview_input`, `test_the_three_binary_types_agree`) onto `Stream(...)`, with a comment recording design.d Decision 3 — that on `of()` they would pass vacuously. Verify each still fails if the corresponding type is removed from `_normalize`'s scalar tuple.
- [x] 2.3 Add the arity tests the new semantics need: `Stream.of([1, 2])` yields one list element; `Stream.of(g)` yields the generator object without advancing it; `Stream.of([1, 2])` and `Stream.of([1, 2], [3, 4])` differ only in element count. Verify all three fail against the current `of()` and will pass after 3.1.

## 3. Flip the semantics

- [x] 3.1 Replace `Stream.of()`'s body with `return Stream(list(args))`, deleting the `len(args) == 1` branch. Verify the three tests from 2.3 now pass.
- [x] 3.2 Rebuild `Stream.iterate()` to return `Stream(_make_iterator(seed, nxt))`. Verify `tests/` covering `iterate()` pass and that an infinite `iterate()` still composes lazily rather than hanging.
- [x] 3.3 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src`. Verify all four are clean.

## 4. Specs

- [x] 4.1 Confirm the `stream-construction` delta in this change matches what landed: arity requirement generalized to every arity, scalar and iterable requirements rebased onto `Stream(...)`, "Single argument" scenario gone. Verify `openspec validate --changes make-stream-of-atomic` passes.
- [x] 4.2 Spot-check three of the 24 swept specs against their own tests to confirm the examples still illustrate what the requirement says. Verify no `Stream.of(` remains in `openspec/specs/**` except where the atomic meaning is intended.

## 5. README

- [x] 5.1 Rewrite the `of(*args: T)` row (line ~201): drop the ~8 lines of divergence prose, state that it matches Java's `of(T...)`. Verify no sentence in the row still describes spreading.
- [x] 5.2 Add the sources prose section before the parity tables, per design.md Decision 6, documenting `Stream(source)` as a Python-native entry point with no Java counterpart in the tables' scope. Verify it covers the same source kinds as the Features bullet at line ~60.
- [x] 5.3 Fix the three passages that argue *from* `Stream.of()` being the source entry point: the `### The generate() function` section (line ~122), `generate()`'s parity row (line ~188), and `ordered()`'s parity row (line ~203). Verify by grepping README above `## Migration` for `Stream.of()` and confirming every remaining hit means the atomic form.
- [x] 5.4 Sweep the nine live README examples (lines ~26, 82, 93, 100, 222) to `Stream(...)`. Verify the opening usage example still runs as written.
- [x] 5.5 Add the Migration entry: `Stream.of()` is now atomic at every arity, the break is **silent**, and the fix is `Stream.of(x)` -> `Stream(x)` for any iterable argument. Verify it follows the format of the three existing silent-break entries.

## 6. Close the roadmap item

- [x] 6.1 Move `roadmap/items/stream-of-arity-semantics.md`'s prose into `roadmap/decisions.md` as a new top entry, recording what shipped and the four decisions from design.md — including the rejected `StreamSupport` framing, which the archive would not otherwise carry. Delete the item file.
- [x] 6.2 Run `python tools/roadmap_index.py` and `uv run pytest tests/test_roadmap.py`. Verify the regenerated index shows Now with four items and the remaining ranks are contiguous.

## 7. Verification

- [x] 7.1 Run the full gate on both legs: `uv run pytest`, `uv run pytest --cov-fail-under=98`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`, and `uv run --python 3.14t pytest`. Verify all pass.
- [x] 7.2 Grep the whole tree for `Stream.of(` and confirm every remaining occurrence is either intentionally atomic, inside the denylist, or in the archive. Every non-archive, non-denylisted hit outside this change's own planning docs falls in one of: `openspec/specs/stream-construction/spec.md` (atomic-meaning requirement text), `README.md` above `## Migration` (3, all atomic-meaning) and below it (7, historical prose, denylisted), `roadmap/decisions.md` (denylisted, append-only), `tests/test_of.py` (the zero-/multi-arg/kwargs cases left alone by design, plus the new arity tests added in 2.3), and `tests/typing/bad_stream_map.py` (one pre-existing multi-arg call, semantics unchanged). The original 1,084/18/10 estimate predates the three arity tests this change adds, so the literal digit total in the original task text no longer applies verbatim; every occurrence was checked individually instead.
- [x] 7.3 Confirm the change lands as **one commit** per the roadmap item's gate — source, tests, specs, README and roadmap together. `git status` shows exactly the touched paths (`src/snakestream/stream.py`; all of `tests/**` swept plus `tests/test_of.py`'s split and new arity tests; 25 `openspec/specs/**` files including the `stream-construction` sync; `README.md`; `roadmap/decisions.md` and the deleted `roadmap/items/stream-of-arity-semantics.md`) with nothing unrelated staged — ready for one commit. Committing itself is left for the user to request.
