## 1. Name the third construction shape

- [x] 1.1 Add `Stream._concatenate(self, a, b)` to `stream.py`, binary per design.md Decision 2, setting `_close_handlers` from `a._close_handlers + b._close_handlers` and `_executor` from the operands' modes, then returning `self` or `self.unordered()`. Verify the three statements match what `concat()` does today line for line.
- [x] 1.2 Write its docstring: what a parentless stream inherits, why it returns rather than mutates (the ordering derive, design.md Decision 3), why consuming the receiver is safe here alone, and that the executor assignment must precede the derive (Decision 4). Verify a reader can tell from the docstring alone why `pipeline-immutability` does not apply.
- [x] 1.3 Rewrite `concat()`'s body to `Stream(_concat(a.iterator(), b.iterator()))._concatenate(a, b)`, keeping the eager-iterator comment and the operand invalidation where they are. Verify `uv run pytest tests/test_concat.py tests/test_data_model.py` is green with the constructor parameter still in place. (Post-review: `_concatenate` moved to sit directly after `_derive`, the only other internal way a stream comes into being, restoring the unbroken static-factory run `of`/`empty`/`concat`/`builder`/`iterate`; pure move, body/call site unchanged, and its docstring now names the `_derive`/`_concatenate` pairing so the reason isn't stranded in design.md alone.)

## 2. Drop the parameter

- [x] 2.1 Remove `close_handlers` from `Stream.__init__`, leaving `_close_handlers` initialized to `[]`. Verify `uv run pytest` reports failures only in the tests named in tasks 2.2 and 2.3.
- [x] 2.2 Delete `tests/test_close.py::test_construct_with_initial_close_handlers` — it tests the parameter itself, so it cannot be migrated. Verify no other test in that file constructs with handlers.
- [x] 2.3 Simplify the three subclasses in `tests/test_execution_model.py` that declare `__init__(self, source, close_handlers=None)` and pass both up, plus the two comments at lines ~80 and ~417 describing that shape. Verify the tests still prove what they were written for — that `derive-without-reinit` freed subclass `__init__` signatures — rather than being deleted with the parameter.
- [x] 2.4 Add a test that `Stream(source, [handler])` raises `TypeError`, per the delta's "A handler argument is rejected" scenario. Verify it fails against the old signature.

## 3. Guard what the specs now claim

- [x] 3.1 Add a test for the reverse aliasing direction: register a handler on the concatenation, then `close()` an operand, and assert it is not invoked. Verify it fails if `_concatenate()` assigns `a._close_handlers` instead of building a new list.
- [x] 3.2 Add a test that a concatenation of two `parallel()`, `unordered()` operands is still parallel, so mode and ordering are asserted together. Verify it fails if the executor assignment is moved after the ordering derive (design.md Decision 4).
- [x] 3.3 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run ty check src`. Verify all four are clean.

## 4. Specs

- [x] 4.1 Confirm the two deltas in this change match what landed. Verify `openspec validate inherit-context-on-concat --type change` passes.
- [x] 4.2 Edit `openspec/specs/stream-close-handling/spec.md`'s `## Purpose` directly, dropping "(including via an explicit `close_handlers` argument)" and the construction-time clause it qualifies. Verify by grepping the file for `close_handlers` and finding only the delta-supplied `TypeError` scenario.

## 5. README

- [x] 5.1 Update the `Building a stream from a source` section, which quotes the constructor. Verify no sentence above `## Migration` still implies a second parameter. (Already correct: it reads `Stream(source)` and never mentioned `close_handlers`; confirmed by grepping the whole pre-Migration section.)
- [x] 5.2 Add the Migration entry: the parameter is gone, the break is **loud** (`TypeError`), and `Stream(source, [h])` becomes `Stream(source).on_close(h)`. Verify it follows the format of the existing loud-break entries and states that subclass `__init__` freedom is unchanged.

## 6. Close the roadmap item

- [x] 6.1 Move `roadmap/items/concat-inheriting-context.md`'s prose into `roadmap/decisions.md` as a new top entry, keeping the `_Stage` rejection and the reason it was *not* rejected. Delete the item file.
- [x] 6.2 Run `python tools/roadmap_index.py` from the repo root and `uv run pytest tests/test_roadmap.py`. Verify Now renders four items numbered **1 to 4** with no gap — ranks 2-5 must each be decremented, not left as they are.

## 7. Verification

- [x] 7.1 Run the full gate on both legs: `uv run pytest`, `uv run pytest --cov-fail-under=98`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`, and `uv run --python 3.14t pytest`. Verify all pass.
- [x] 7.2 Grep `src/` and `tests/` for `close_handlers` and confirm every remaining hit is `_close_handlers`, the attribute, with no reference to a constructor argument left in code or comments. One `_derive()` docstring sentence describing the pre-`derive-without-reinit` problem ("accept the base class's constructor parameters positionally") was reworded to drop its literal `(source, close_handlers)` mention, since a future reader could otherwise misread it as describing the current signature. The gitignored `src/snakestream.egg-info/PKG-INFO` build artifact still carries the old text; it isn't part of the repo.
- [x] 7.3 Confirm the change lands as one commit covering source, tests, specs, README and roadmap. `git status` shows exactly: `src/snakestream/stream.py`; `tests/test_close.py`, `tests/test_concat.py`, `tests/test_execution_model.py`; `openspec/specs/stream-close-handling/spec.md` and `openspec/specs/stream-concat/spec.md`; `README.md`; `roadmap/decisions.md`, `roadmap/README.md`, the four re-ranked item files, and the deleted `concat-inheriting-context.md` — plus the change's own `openspec/changes/inherit-context-on-concat/` folder, untracked. Nothing unrelated staged. Committing is left for the user to request.
