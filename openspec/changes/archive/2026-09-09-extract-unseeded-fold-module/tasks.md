## 1. Create the new module

- [x] 1.1 Create `src/snakestream/unseeded.py` holding `UNSET` and `unseeded()`
      only, moved from `sink.py` with their comment and docstring, and with no
      package imports; verify with
      `python -c "from snakestream.unseeded import UNSET, unseeded"` and that
      `grep -n "^from snakestream" src/snakestream/unseeded.py` returns nothing
- [x] 1.2 Move `UnseededSink` into `terminals.py` as `_UnseededSink`, defined
      above its three subclasses, and repoint `ReduceSink`, `MinMaxSink` and
      `FindSink` at the new name; verify
      `grep -rn "UnseededSink" src/ | grep -v "_UnseededSink"` returns nothing

## 2. Remove them from `sink.py`

- [x] 2.1 Delete the `UNSET`/`unseeded()`/`UnseededSink` definitions from
      `sink.py`, leaving its module docstring **unchanged** (it never mentions
      them — there is nothing to trim, and it gains no pointer to
      `unseeded.py`); verify `grep -n unseeded src/snakestream/sink.py` returns
      nothing and `grep -n "^UNSET" src/snakestream/sink.py` returns nothing

## 3. Update importers

- [x] 3.1 Update `stream.py` to import `UNSET` from `snakestream.unseeded`
      instead of `snakestream.sink`, and fix the `stream.py:55` comment that
      names `sink.py` as `UNSET`'s home to name `unseeded.py` instead; also fix
      `unseeded()`'s own docstring, which says the rule reaches terminals
      "through `UnseededSink` below" — it is no longer below it
- [x] 3.2 Update `terminals.py` to import `UNSET`/`unseeded` from
      `snakestream.unseeded`, keeping its `TerminalSink` import from
      `snakestream.sink` (which `_UnseededSink` now uses in place)
- [x] 3.3 Update `collectors.py` to import `UNSET`/`unseeded` from
      `snakestream.unseeded`
- [x] 3.4 Verify no remaining reference to `UNSET`/`unseeded`/`UnseededSink`
      imports `snakestream.sink`:
      `grep -rn "from snakestream.sink import" src/snakestream | grep -E "UNSET|unseeded|UnseededSink"`
      returns nothing

## 4. Verify

- [x] 4.1 Run `uv run ruff check .` and `uv run ruff format --check .` and
      verify both pass
- [x] 4.2 Run `uv run ty check src` and verify it passes with no new errors
- [x] 4.3 Run `uv run pytest --cov-fail-under=98` and verify the full suite
      passes with coverage unchanged
- [x] 4.4 Run `uv run pytest tests/test_name_visibility.py` and verify it
      passes (no module imports a name that should be underscored)

## 5. Close the roadmap item

- [x] 5.1 Move `roadmap/items/sink-sentinel-placement.md`'s prose into
      `roadmap/decisions.md` as a new top entry, delete the item file, and
      regenerate the index with `python tools/roadmap_index.py`; verify
      `uv run pytest tests/test_roadmap.py` passes
