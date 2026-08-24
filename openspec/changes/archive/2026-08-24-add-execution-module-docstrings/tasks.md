## 1. `execution.py` module docstring

- [x] 1.1 Add a 4-5 line module docstring above the imports naming the four
      execution primitives (`stream_through`, `race_through`, `feed_through`,
      `drain`) and the two executors (`Sequential`, `Racing`).
- [x] 1.2 Note that `Sequential.value()` overrides the generic
      `drain(elements(...), terminal)` default with a fused push, and that
      this is the one asymmetry in the protocol (do not restate the
      docstring's own numbers already on `Sequential.value()` — point at it).

## 2. `sink.py` module docstring

- [x] 2.1 Add a 4-5 line module docstring above the imports naming the
      op/sink pair and the `begin`/`accept`/`end` protocol a `Sink`
      implements.

## 3. `ops.py` module docstring

- [x] 3.1 Add a 4-5 line module docstring above the imports stating the file
      holds one `Op` plus one `Sink` per intermediate operation, and
      contains no execution logic (that lives in `execution.py`).

## 4. Verification

- [x] 4.1 Confirm each new docstring is orientation only — it does not
      restate what an existing class docstring in the same file already
      says.
- [x] 4.2 Run `uv run pytest` and confirm the full suite passes with no test
      file edited (this is a documentation-only change).
- [x] 4.3 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 4.4 Run `uv run ty check src`.
- [x] 4.5 Update `roadmap.md`: move this item from **Now** to **Done** with
      a summary, per the project's established roadmap/opsx workflow.
