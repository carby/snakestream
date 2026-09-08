+++
id = "spliterator-round-trip"
title = "`spliterator()` is a one-way door, and the naive way back fails silently"
bucket = "later"
rank = 2
filed = 2026-09-08
blocked_on = "which of four answers the one-way door gets - spread a `Spliterator` source, add a static for it, reject it loudly, or narrow the promise instead"

[refs]
specs = ["stream-spliterator", "stream-construction"]
files = ["src/snakestream/spliterator.py", "src/snakestream/stream.py", "README.md"]
+++

Surfaced 2026-09-08 while exploring
[`stream-of-arity-semantics`](stream-of-arity-semantics.md), from the question of
whether `StreamSupport` belonged in README's parity tables. It did not — see
"What the analysis corrected" below — but tracing why left a real gap behind.

`Spliterator` is public and documented. `Stream.spliterator()` returns one,
`try_split()` returns another, and README's `spliterator()` row promises it "is
also directly usable by a caller who wants manual decomposition". There is no
supported way back:

    Stream.spliterator()  ->  Spliterator
    sp.try_split()        ->  Spliterator
    Stream(sp)            ->  ???

`_normalize()`'s ladder has no branch for it. A `Spliterator` is not in the
scalar set, is not `Iterable`, has no `__next__`, and is not `AsyncIterable`, so
it falls through to the final `else: yield source` and produces **a one-element
stream containing the spliterator object**. Nothing raises. A caller who takes
the manual-decomposition promise up can split a stream and then cannot process
either half as a stream, and the obvious attempt fails silently rather than
loudly — the same shape as the `bytearray`/`memoryview` break that earned its own
Migration entry.

Java closes this loop with `StreamSupport.stream(spliterator, parallel)`, which
is what raised the question. That is where the parity reading stops being useful.

## The four answers

Blocked on the decision, not on effort — but the four are not variations of one
approach, and the cheapest is not obviously the best.

| | approach | what it costs |
|---|---|---|
| a | `_normalize()` grows a `Spliterator` branch, draining it via `try_advance()` | also has to decide whether the resulting stream inherits `ORDERED` from `characteristics()` and whether `_estimate_size()` reads `estimate_size()`. Real design, not a branch. |
| b | a static shaped like `StreamSupport.stream()` | invents a name with no counterpart on any type snakestream has; the 0.3.0 removal of `stream_of()` "for getting closer to the java api" is the cautionary precedent. |
| c | leave it one-way, but make the silent case **loud** — reject a `Spliterator` source | cheapest honest option. Keeps the promise narrow rather than keeping the promise. |
| d | nothing, and narrow README's `spliterator()` row to say decomposition is read-only | no code; admits the row currently overpromises. |

## Sequencing

Better filed after `make-stream-of-atomic` lands. That change makes
`Stream(source)` the *documented* construction entry point, which is what turns
this from an obscure internal detail into a visible defect in a documented
surface. Reading (c) or (d) as sufficient is much harder to justify once the
constructor is the thing README tells callers to use.

## What the analysis corrected

The exploration reached this by way of a framing that did not survive checking,
and the checks are worth not repeating. `StreamSupport` was considered as the
parity home for the normalizing constructor and rejected three times over:

- **There is no totality defect.** README's tables claim totality over `Stream`,
  `BaseStream`, `Collectors` and `Comparator` — four types, named. `StreamSupport`
  is out of scope by declaration, not missing.
- **The wholesale skip is only partly wrong about it.** `StreamSupport` has eight
  statics; six are `intStream`/`longStream`/`doubleStream` overloads that the
  stated autoboxing reason genuinely covers. Only the two generic `stream(...)`
  overloads borrow a reason that does not fit. **Corrected in README's
  wholesale-skip paragraph 2026-09-08**, which now separates the six from the two
  and points here for the two; the paragraph no longer needs revisiting whichever
  answer above is chosen.
- **`Stream(source)` is not `StreamSupport.stream()`.** Java's takes a
  `Spliterator` plus a parallel flag. `Stream(source)` takes anything at all, does
  not accept a `Spliterator`, and the parallel flag is `.parallel()`, a separate
  axis. Claiming the row would have been a parity claim that is not true.

So there is no `StreamSupport` item to file, and this is not one. Six of its
eight methods are correctly gone with the primitive streams — there is one kind
of `Stream` here — and what remains is not a missing method but a documented
object with no supported way back into a pipeline.
