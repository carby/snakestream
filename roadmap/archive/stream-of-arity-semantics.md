+++
id = "stream-of-arity-semantics"
title = "`Stream.of()` becomes atomic at every arity"
filed = 2026-08-20
closed = 2026-09-08
outcome = "shipped"
shipped_as = "make-stream-of-atomic"
+++

**`Stream.of()` becomes atomic at every arity** (closed 2026-09-08; filed
2026-08-20). Shipped as `make-stream-of-atomic`.

`Stream.of([1, 2])` used to spread the single list into two elements while
`Stream.of([1, 2], [3, 4])` yielded two lists — the number of arguments
changed what an argument *meant*, there was no way to express a stream of
exactly one iterable, and Java's `of(T...)` treats every argument
atomically. **Java parity won**, unblocked 2026-09-08 after being
decision-blocked rather than effort-blocked since filing: the spreading form
was the primary documented idiom, used in nearly every README example,
throughout the test suite, in 25 live capability specs, and by
`Stream.iterate()`'s own body, which is why the call was deferred rather than
made in passing.

**The break is silent and total.** `Stream.of(x)` for any iterable `x`
changes from spreading to a single element, with nothing raising.
`of()`'s body became `return Stream(list(args))`, deleting the
single-argument delegation branch entirely rather than special-casing it
away, and `Stream.iterate()` was rebuilt onto `Stream(_make_iterator(...))`
directly since `Stream.of(*gen)` would drain an infinite generator eagerly at
the call site — the only reason `iterate()` couldn't simply keep calling
`of()`.

**The migration target could only be the constructor.** `Stream(source)` was
already public — the only name `snakestream/__init__.py` exported — and
README's own Features bullet already described building a stream from a
List, Generator, AsyncGenerator, Iterator, AsyncIterator or bare object
through it; the change stopped concealing a name that had been hiding inside
`of()`'s row rather than adding one. A new static (`Stream.from_source`,
`Stream.of_iterable`) was rejected: it would have re-added under a new
spelling the free function `stream_of()` deleted in 0.3.0 "for getting closer
to the java api," and invented a name with no Java counterpart when an
existing public one already did the job.

**The sweep was mechanical because the two calls were, until the flip
landed, the same call.** `Stream.of(X)` -> `Stream(X)` was
behaviour-preserving by construction for every single-argument site,
whatever `X` was — 1,084 of the 1,112 non-archived occurrences of
`Stream.of(` in the tree, every one single-line — so the sweep ran as a
regex ahead of the semantics flip, with the test suite as the check, rather
than as a per-site judgement call. The 22 scalar-set sites (`dict`, `str`,
`bytes`, `bytearray`, `memoryview`, and the non-iterable `None`/`int` cases
alongside them) were excluded from the sweep on purpose: after the split
`Stream.of(x)` agrees with `Stream(x)` on every scalar `x` by construction,
since `of()` no longer spreads anything, so a scenario or test still written
against `of()` would hold whatever normalization did and guard nothing. Nine
of those sites were tests in `tests/test_of.py` guarding
`define-and-guard-stream-sources`, including the documented *silent*
`bytearray`/`memoryview` break; left on `of()`, they would have quietly
stopped testing anything.

**`stream-construction` took a requirement delta; the other 24 live specs
were swept in place.** A delta records a requirement change, and the other
24 specs' `Stream.of([...])` occurrences were illustrative examples inside
scenarios whose requirements did not change — correcting them directly was
weighed against a delta per capability and rejected, since the latter is
protocol-pure but forces `MODIFIED Requirements` to carry 24 entire
requirement blocks copied verbatim, exactly the shape that silently loses
detail at archive time.

**`StreamSupport` was considered and rejected as a home for documenting
`Stream(source)`**, on three checks. First, is there a totality defect to
repair — no: README's parity tables claim totality over `Stream`,
`BaseStream`, `Collectors` and `Comparator`, four types, named, and
`StreamSupport` is out of scope by declaration, so no row is missing.
Second, is the wholesale skip of `StreamSupport` wrong about it — only
partly: six of its eight statics are primitive specializations the stated
autoboxing reason genuinely covers, and only the two generic `stream(...)`
overloads borrow a reason that doesn't fit, which is a wording fix rather
than a hole to move into. Third, and decisive: is `Stream(source)` actually
`StreamSupport.stream()` — no. Java's takes a `Spliterator` plus a parallel
flag; `Stream(source)` takes anything at all, does not accept a
`Spliterator`, and the parallel flag is `.parallel()`, a separate axis.
Claiming the row would have been a parity claim that wasn't true. The real
counterparts of `Stream([1, 2, 3])` are `Collection.stream()` and
`Arrays.stream(T[])` — methods on types this library does not have, and
outside the tables' scope on any of the four types they cover. `Stream(source)`
is documented in prose instead, before the parity tables, on the precedent
already set one section earlier for Python's dunder methods.

Typing was out of scope: `ty` infers `Stream[Unknown]` for `Stream.of(...)`,
`Stream(...)` and `Stream.of(*args)` alike, both before and after, so the
migration cost nothing statically. `generic-stream-typing`'s scenario
claiming otherwise is a pre-existing defect, unrelated to this change and
left alone. `Stream.__init__`'s exposed `close_handlers` parameter was also
left alone deliberately: this change already carried one silent break, and a
second loud one plus its own Migration entry would have bought nothing this
change needed.
