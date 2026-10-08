+++
id = "async-predicate-short-circuit-tests"
title = "Covered the async-predicate short-circuit branches of the `*_match` family"
filed = 2026-08-04
closed = 2026-08-04
outcome = "shipped"
+++

Added tests covering the async-predicate short-circuit branches of
`all_match`, `none_match`, and `any_match` (`stream.py:255,267,283`) that
were previously only exercised by synchronous predicates.
