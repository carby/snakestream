+++
id = "hypothesis-property-tests"
title = "Added property-based tests with `hypothesis`"
filed = 2026-08-11
closed = 2026-08-11
outcome = "shipped"
+++

Added property-based tests with `hypothesis` for `map`, `filter`, `reduce`,
`sorted`, `distinct` against a plain-Python reference oracle, covering
edge cases hand-written tests miss (empty/single-element streams,
duplicate keys, async callables).
