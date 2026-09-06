+++
id = "java-9-additions"
title = "Java 9 additions — six, not four"
bucket = "later"
rank = 2
filed = 2026-08-20
updated = 2026-09-05
blocked_on = "whether Java 9 becomes a tracked parity effort, gets cherry-picked for independent merit, or stays opportunistic with Java 8 as the destination"

[refs]
specs = ["stream-ordering", "collector-mapping", "stream-iterate"]
files = ["src/snakestream/stream.py", "src/snakestream/collectors.py", "README.md"]
+++

`Stream`: `takeWhile(predicate)`, `dropWhile(predicate)`, `Stream.ofNullable(t)`,
and the 3-arg `iterate(seed, hasNext, next)` overload (distinct from the
already-implemented 2-arg `iterate(seed, next)`). `Collectors`:
`filtering(predicate, downstream)` and `flatMapping(mapper, downstream)`, which
this item omitted until 2026-09-05.

**Not gated on Java 8 any more — Java 8 is closed** (2026-09-05; see
[`decisions.md`](../decisions.md): zero gap rows across all three README
tables). README gates Java 9 on "some sort of feature parity with Java 8" and
that gate is now met outright rather than argued. What keeps this in **Later**
is the bucket's own criterion: it is **undecided**, not blocked. Nobody has
called whether Java 9 becomes a tracked effort the way `Collectors` parity once
was, whether only the items with independent merit get cherry-picked, or whether
Java 8 is the destination and Java 9 stays opportunistic. That call is the entry
ticket, and it is deliberately not made here.

**Effort, for whoever makes it:** four of the six are near-free — `ofNullable`
and the 3-arg `iterate` are a static and an overload widening in `stream.py`,
and `filtering`/`flatMapping` are downstream-deriving collectors on `mapping()`'s
exact shape (combiner and characteristics derived from the downstream). Only
`takeWhile`/`dropWhile` carry design weight: both are `order_sensitive` in the
sense `limit`/`skip`/`distinct` are — the answer depends on an element's
*position* — so each needs an `Ordering` declaration and forces a
`split_point()` in an ordered fork/join pipeline, and `takeWhile` needs
`limit`'s cancellation in its sink besides. That is declaring two ops into
machinery built for them, not new machinery.
