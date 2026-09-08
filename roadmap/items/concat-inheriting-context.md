+++
id = "concat-inheriting-context"
title = "`close_handlers` is a constructor parameter with one caller"
bucket = "now"
rank = 1
filed = 2026-09-08
gate = "`Stream(source)` one parameter wide; `concat()` setting handlers, mode and ordering through one named operation instead of three mechanisms; the merged handler list's non-aliasing under test; and a README Migration entry for the loud `TypeError`"

[refs]
changes = ["derive-without-reinit", "make-stream-of-atomic"]
specs = ["stream-concat", "stream-close-handling", "pipeline-immutability"]
files = ["src/snakestream/stream.py"]
+++

Surfaced 2026-09-08, immediately after
[`make-stream-of-atomic`](../decisions.md) made `Stream(source)` the
*documented* construction entry point. The parameter was invisible while the
constructor was; it is not any more.

`Stream.__init__(self, source, close_handlers=None)` has exactly one production
caller — `Stream.concat()`. `of()`, `empty()`, `iterate()` and
`StreamBuilder.build()` all pass a source alone, and `_derive()` never touches
it, because `copy()` carries `_close_handlers` forward by reference.

**The parameter is the symptom. The defect is that `concat()` sets three
sibling attributes by three different mechanisms**, with no principle picking
between them:

| state | how `concat()` sets it | how `_derive()` sets it |
|---|---|---|
| `_source` | constructor argument | copy, shared |
| `_close_handlers` | **constructor parameter** | copy, shared by reference |
| `_executor` | **direct assignment** | copy, or the `executor` argument |
| ordering | **a `.unordered()` derive** | lives in the chain |

`_close_handlers` is the only piece of stream state with a constructor
parameter, and its two siblings in the same function do without one.

## Why `concat()` is the only place this arises

There are exactly two ways a stream comes into being, and they match Java's
two `AbstractPipeline` constructors: from a source (`Stream(source)`, ours
public where Java's is not) and from another stream (`_derive()`, which
copies where Java links stages). Java keeps the close action and the parallel
flag on the *source stage*, shared downstream; `copy()` gets the same sharing
without a stage graph, which is why `_derive()` only assigns what actually
differs and needs nothing passed to it.

`concat()` is a third shape neither constructor covers: **from a source, with
context inherited from streams that are not its parent.** It cannot copy an
operand — the result is a plain `Stream` even when both operands share a
subclass, since `type(a)` and `type(b)` have no principled tie-break
(`stream-concat`) — and it cannot construct plainly, because it owes the
operands their handlers and their mode.

## The shape to land

Both paths are construct-then-mutate; that is not the problem.
`_derive()` reads as principled because the mutation sits inside a named
operation whose docstring states the rules. `concat()` does the same kind of
mutation in the open. Give the third shape its name — `concat()`'s docstring
already enumerates what is inherited and why each part arrives as it does, so
the concept exists in prose with no home in code:

    concatenated = Stream(_concat(a.iterator(), b.iterator()))._inheriting(a, b)

with `_inheriting()` folding the handler merge, the mode decision and the
ordering derive into one place, and the constructor dropping to
`Stream(source)`.

**Load-bearing and easy to lose while rearranging:** the merged handler list
must be a **new** list. `a._close_handlers + b._close_handlers` builds one
today; assigning an operand's list directly would alias the concatenation's
handlers to it, so a later `on_close()` on the concatenation would silently
register on the operand as well. No current test would catch that.

## What the analysis rejected

A `_Stage`-style value object holding source, chain, executor and handlers,
with derivation as `replace()`. **Rejected on cruft, not on performance** —
the performance objection was checked and does not hold. Pipeline state is
read only inside `stream.py`, and the chain reaches `execution.py` by value
once per terminal rather than per element, so the extra allocation would land
once per `_derive()` call — per stage, not per element. Every regression this
repo has measured and acted on was per-element (the +125% on `count()` from
composing then draining; the ~3% on the segment-sign twins). This is not in
that class.

What sinks it is that it buys nothing. `copy()` already expresses "carry all
shared context forward", including subclass attributes it does not know about.
A `_Stage` would have to answer a question `copy()` never asks — which
attributes are pipeline state — and answer it awkwardly: `_consumed` is
per-reference and would sit outside, `_size_hint` belongs to the raw source,
and subclass attributes belong to nobody in particular. That is a boundary
written down where none needs to exist.

It becomes the right answer the moment a **second** parentless construction
site appears, and nothing in this item blocks that: extracting from two call
sites that already agree is the honest moment for it. Today there is one, and
`concat()` is the only binary operation in the API (`__add__` delegates to
it).

## Cost

A loud break: `Stream([1, 2, 3], [handler])` starts raising `TypeError`.
`tests/test_close.py`'s `test_construct_with_initial_close_handlers` tests the
parameter itself and is deleted rather than migrated; three subclasses in
`tests/test_execution_model.py` that pass `(source, close_handlers)` up to
`super().__init__()` get simpler. The freedom `derive-without-reinit` bought —
a subclass may define any `__init__` signature — is untouched; what goes is
the option of seeding handlers at construction, and `on_close()` is the
public, documented way to do that.
