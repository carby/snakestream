+++
id = "stream-of-arity-semantics"
title = "`Stream.of()`'s arity-dependent semantics"
bucket = "later"
rank = 3
filed = 2026-08-20
updated = 2026-08-31
blocked_on = "whether Java parity is worth breaking essentially every call site in the docs and tests, or whether the divergence is declared permanent"

[refs]
specs = ["stream-construction"]
files = ["src/snakestream/stream.py", "README.md"]
+++

`Stream.of([1, 2])` spreads the single collection into two elements, while
`Stream.of([1, 2], [3, 4])` yields two lists. The number of arguments changes
what the arguments mean, there is no way to express a stream of exactly one
list, and Java's `of(T...)` treats every argument atomically.

Decision-blocked rather than effort-blocked, which is what this bucket is for.
The spreading form is not an oversight: it is the primary documented idiom, used
in nearly every README example and throughout the test suite, and
`Stream.iterate()` is built on it. Changing it would be a far larger break than
the `str`/`bytes` and kwargs changes already in the migration log, touching
essentially every call site in the docs and tests. Needs an explicit call on
whether Java parity is worth that, or whether the divergence should be declared
permanent.

**Narrowed 2026-08-31: the behaviour is now documented in README's `of()` row.**
That was a defect independent of this decision — the row described Java's
semantics, so the divergence used by every example in the file was invisible to
a reader. Documenting it does not close this item; what remains is the call on
whether to keep it. Surfaced 2026-08-20 in the same code-quality read that
produced the first batch of **Now** items, all since closed.
