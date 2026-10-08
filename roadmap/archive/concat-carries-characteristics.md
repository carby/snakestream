+++
id = "concat-carries-characteristics"
title = "`Stream.concat()` carries its inputs' characteristics (`concat-carries-characteristics`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "concat-carries-characteristics"
+++

**`concat-carries-characteristics`** (2026-08-31) — `Stream.concat(a, b)`
returned a base `Stream` with an empty chain and the default executor, so it
carried its operands' elements and close handlers and nothing else they knew
about themselves. Java's one sentence is the whole contract: the result *"is
ordered if both of the input streams are ordered, and parallel if either of
the input streams is parallel"*. First of question 7's three, and the reason
it went first: **it was wrong today with zero subclasses in play**, where the
item that opened the session only bit a subclass the repo does not have.

Measured before: `concat(a.parallel(), b.parallel()).is_parallel()` was
`False`, and `concat(a.unordered(), b.unordered())` was ordered — so
`unordered()`, the documented performance lever, was silently revoked past the
concat boundary and the caller paid a barrier they had explicitly opted out of.

**The two halves arrive by different mechanisms, and the asymmetry is not
new.** Mode is a value on the stream and is assigned; ordering is positional
and has to occupy a position, so the result seeds its chain with the stage
`unordered()` queues. That is not a stylistic pick: `pipeline-immutability`
forbids carrying the characteristic as state beside the chain, so a field was
never available. It reads oddly — a chain the caller did not write — but it is
correct in Java's own terms, `unordered()` being a pipeline stage there for
exactly this reason.

**BREAKING, and the silent wrong answer is why.** `concat()` now consumes both
operands. It previously left them live over the source the concatenation also
drew from, so `await a.collect(to_list())` returned `[1, 2, 3]` and the
concatenation then yielded `[4, 5]` — a shortened result with no exception
anywhere. Java raises here; `AbstractPipeline` marks the operands linked.
`iterator()` is untouched, its non-destructive composition being a
`stream-iterator` requirement that `collect(to_generator)` and `flat_map`
depend on, so the invalidation belongs to `concat()`.

One decision recorded rather than fixed: the result stays a base `Stream` even
when both operands share a subclass. `type(a)` and `type(b)` may differ with no
principled tie-break, a subclass constructor may want arguments `concat()`
cannot supply, and Java returns an internal type for the same reason. It has no
executable guard and cannot have one — nothing would make `concat()` start
returning a subclass by accident — so the spec is the record.
