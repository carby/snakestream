+++
id = "stream-of-dead-branch"
title = "Removed a dead branch from `Stream.of()`"
filed = 2026-08-03
closed = 2026-08-03
outcome = "shipped"
+++

`Stream.of()` had a dead branch, `if args and len(args) == 0: pass`
(`stream.py:40-41`), which could never be true and just duplicated the
no-op fallthrough of the `else` branch. Removed.
