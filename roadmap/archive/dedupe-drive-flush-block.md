+++
id = "dedupe-drive-flush-block"
title = "Rejected: deduplicating `BaseStream._drive()`'s bridge-buffer flush block"
filed = 2026-08-20
closed = 2026-08-20
outcome = "declined"
+++

**Rejected: deduplicating `BaseStream._drive()`'s bridge-buffer flush block.**
The same roadmap item proposed a local closure for the two verbatim four-line
flush blocks at `base_stream.py:120-123` and `127-130`. `_drive()` has to
`yield` mid-loop, so it cannot use `_copy_into()` at all, and every
single-flush-site form puts a per-element object on the `iterator()` /
`to_generator()` / parallel-branch path — the in-loop flush runs once per
element; only the post-`end()` flush is once per stream. Measured on the
established harness (Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops,
best of 5, three independent invocations), baseline reproducing the
1,907 ns/element `add-callsite-dispatch` recorded:

| Variant | ns/element (3 runs) | vs baseline |
|---|---|---|
| **Baseline** — duplicated block, as shipped | 1929, 2091, 1907 | — |
| Single site via **async-generator** closure | 3002, 2932, 3009 | **+50%** |
| Single site via **sync-generator** closure | 2137, 2123, 2217 | **+10%** |

This is the same trade `GeneratorBridgeSink`'s docstring already records
rejecting for a `drain()` returning a fresh list. By contrast `_copy_into()`,
entered once per stream, measured free: 1686/1620/1741 baseline vs.
1625/1654/1739 with the helper on a `count()` terminal — noise in both
directions. **Do not re-propose the flush dedup without new figures.**
