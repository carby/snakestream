+++
id = "stream-of-arity-semantics"
title = "`Stream.of()`'s arity-dependent semantics"
bucket = "now"
rank = 1
filed = 2026-08-20
updated = 2026-09-08
gate = "the break lands whole: `Stream.iterate()` rebuilt off the spreading form, every README example and test call site updated, and a README Migration entry, all in the same commit"

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

**Unblocked 2026-09-08: Java parity wins.** `of(*args)` becomes atomic —
`Stream.of([1, 2])` yields one list — and the break is accepted rather than
argued down. The cost is known and unchanged from the paragraphs above: nearly
every README example, nearly every test call site, and `Stream.iterate()`'s
body, which is built on the spreading form and has to be rebuilt off something
else. It lands as one commit with a README Migration entry.
