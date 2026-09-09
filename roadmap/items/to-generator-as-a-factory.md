+++
id = "to-generator-as-a-factory"
title = "to_generator is the one collector called without parens"
bucket = "now"
rank = 3
filed = 2026-09-09

[refs]
files = ["src/snakestream/collector.py", "src/snakestream/collectors.py"]
+++

Every collector factory in `collectors.py` is called: `collect(to_list())`,
`collect(to_map(...))`. `to_generator` is the one exception - it is a bare
`StreamingCollector` instance in `collector.py`, so the call site is
`collect(to_generator)`, no parens, and a caller has to remember which one it
is.

The fix is to make `to_generator` a factory too: a function in `collectors.py`
returning a `StreamingCollector` instance, matching how every other collector
is obtained. `_stream()`, the plain function the instance currently wraps,
moves with it.

**This buys exactly one thing** - call-site symmetry across every collector.
It does not buy less surface on `maybe_aclosing`: `_stream()` still needs it,
and `collectors.py` is as separate from `execution.py` as `collector.py` is,
so `maybe_aclosing` stays a bare, cross-module name either way.

## What has to move together

- `collect(to_generator)` -> `collect(to_generator())` at every call site:
  every test file that imports it (`test_map`, `test_filter`, `test_flat_map`,
  `test_concat`, `test_of`, `test_iterate`, `test_integration`,
  `test_racing_delivery_order`, `test_collect`) and the README quickstart.
- README's API table and the Collectors-section paragraph explaining
  `to_generator` as "the one exception" - both currently describe it as a bare
  instance kept beside the type; both need to say it is a factory instead.
- CLAUDE.md's Collectors paragraph, which gives the current placement as
  deliberate ("it sits in `collector.py` beside the type rather than with the
  factories... The one exception is `to_generator`..."). That reasoning no
  longer applies once it is a factory, not an instance.
- A README Migration entry, same commit - `collect(to_generator)` stops
  working and `collect(to_generator())` is required; there is no compatible
  overlap to shim.

`collector.py` ends up holding only the protocol - `Collector`, `CollectorSink`,
`StreamingCollector` - with zero instances of anything, which is the same shape
`collectors.py`/`collector.py` already claim for every other collector.
