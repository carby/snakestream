## Context

See proposal.md — Why. The state this design starts from, in three facts:

1. `Stream.collect()` (`stream.py:668-689`) has three shapes: a `Collector`, a
   `StreamingCollector`, and the three-argument supplier/accumulator/combiner
   form. The middle one is reached by exactly one value, `to_generator`, and its
   whole body is `return collector(self.iterator())`.
2. `to_generator` is `StreamingCollector(_stream)`, and `_stream` is an async
   generator that re-yields its argument inside `maybe_aclosing`.
3. `collector.py` imports `maybe_aclosing` from `execution.py` (`:14`) for
   `_stream` and for nothing else.

This is a deletion, not a redesign. What needs deciding is whether the deletion
loses anything, and what shape the migration takes.

## Goals / Non-Goals

**Goals**

- `collect()` has one contract: it takes a `Collector`, it returns an awaitable.
- `collector.py` holds only the protocol, with no instances, no module-level
  functions, and no import from the execution layer.
- Every existing `collect(to_generator)` call has a migration that is strictly
  better at the call site — shorter, no import, and faster.

**Non-Goals**

- Any change to `iterator()`, `__aiter__`, `Stream.concat()`, or the executor
  protocol. `iterator()` is the destination, and it is untouched.
- Any change to `Collector`, `CollectorSink`, `Characteristics`, or any of the
  ~20 factories in `collectors.py`.
- A deprecation period or a shim. See Decision 3.

## Decisions

### Decision 1: Delete, rather than make `to_generator` a factory

Roadmap item `to-generator-as-a-factory` proposed the factory fix. This design
rejects it and inverts the item's conclusion.

There are two asymmetries between `to_generator` and every other collector, not
one:

    collect(to_list())        called          returns an awaitable
    collect(to_generator)     bare instance   returns an AsyncGenerator
    collect(to_generator())   called          returns an AsyncGenerator

The parens are the visible asymmetry and the harmless one — getting it wrong
raises immediately. The return contract is the invisible one and the harmful
one: `await` an async generator, or `async for` over a coroutine. The factory
fix addresses only the first, and by making the call site look identical to
`collect(to_list())` it removes the one visual cue that the second exists. The
item's own summary — "this buys exactly one thing, call-site symmetry" — is
therefore optimistic: it buys the appearance of symmetry over a difference that
is real.

Deleting the value removes both asymmetries by removing the case.

**Alternative considered — keep it and document the parens as deliberate.**
Rejected: it leaves the +31% per-element layer, the extra `collect()` branch and
overload, and the exception text in six specs, in exchange for a duplicate
spelling of a method the library already has.

**Alternative considered — move it to `collectors.py` as a factory (item's
option A, and a variant keeping it in `collector.py`).** Rejected for the reason
above. The item's stated consolation, that `collector.py` would then hold "zero
instances of anything", is achieved by deletion too — and deletion additionally
drops the module's `execution.py` import, which the factory move explicitly does
not ("it does not buy less surface on `maybe_aclosing`").

### Decision 2: `iterator()` is the migration target, and it is behaviourally identical

The concern a reviewer should raise is teardown: `_stream` wraps the composition
in `maybe_aclosing`, and `iterator()` returns the composition raw. Does dropping
the wrapper lose a close?

It does not, for two reasons that compose:

- **The source is already closed by the composition itself.**
  `_stream_through()` wraps its source in `maybe_aclosing` (`execution.py:124`),
  and both fork-join paths do the same (`:297`, `:458`). Nothing about source
  teardown depends on `_stream`.
- **The wrapper's own close has exactly the same trigger as the thing it
  wraps.** `_stream`'s `maybe_aclosing` fires when `_stream` is closed, and
  `_stream` is closed when — and only when — the caller closes it or it is
  garbage-collected. That is precisely the condition under which the caller
  would have closed the composition directly. So the wrapper converts "the
  caller closes the composition" into "the caller closes the wrapper, which
  closes the composition": one more hop, the same guarantee.

The library has already relied on this. `pipeline-composition`'s `flat_map`
requirement exists because the extra layer was a *liability*: the inner stream
had to be iterated through its own composition "rather than through a
`collect(to_generator)` wrapper, so there is a single generator layer to close"
(decisions.md, the `flat_map` inner-generator leak). Internal code stopped using
`to_generator` for exactly this reason; this change finishes the job at the
public surface.

The one capability that genuinely disappears is `to_generator(some_iterable)` as
a **standalone adapter** — calling it directly on an arbitrary `AsyncIterable`
rather than passing it to `collect()`. Only two tests use it that way
(`tests/test_collect.py:41-62`); no library code and no documented API does. It
is not replaced, because `async for` over the iterable is the replacement.

### Decision 3: Break loudly, with no shim

Removing the name gives `ImportError` at import time, before any stream is
built. That is the same break shape, and the same reasoning, as the
`collectors.py` split (README Migration, 0.3.5 -> next): one path to each name,
no re-export.

A shim was considered and rejected on grounds the split already settled — and
here it is worse than there. The only shim that could preserve
`collect(to_generator)` is keeping the value, which is the whole thing being
removed; and a shim that preserved the *name* while changing its behaviour
would turn an import-time error into a runtime type confusion, which is the
opposite of the trade this change is making.

### Decision 4: Two spec deltas are REMOVED + ADDED, not MODIFIED

`stream-iterator` and `terminal-sinks` each carry a scenario whose entire
subject is `to_generator` ("to_generator matches iterator()", "`to_generator`
still composes through the bridge"). A MODIFIED requirement replaces its whole
block but may not *drop* a scenario the current spec still has — the validator
refuses it, so that archiving can never silently lose one. Both requirements are
therefore removed and re-added under a name that states what changed:

- `Operations that need a generator use the executor's element-producing form`
  -> `` `iterator()` and `concat()` use the executor's element-producing form ``
  (its subject list shrank from three to two).
- `iterator() works identically for sequential and parallel streams`
  -> `iterator() works identically for sequential and parallel streams, and is
  the only route to the composed generator` (it gains the uniqueness clause the
  deletion establishes).

Each dropped scenario is replaced by one asserting the new negative — that no
collector composes through the bridge, and that there is no second route to the
composed generator — so the deletion is pinned by a test rather than merely
absent. The other four deltas are ordinary MODIFIED blocks; `collector-protocol`
additionally REMOVEs "`to_generator` is the one non-`Collector` collector"
outright, since that requirement has no successor.

## Risks / Trade-offs

**[Coverage] `tests/test_collect.py:56`, `test_to_generator_no_aclose_on_source`,
is deleted, and it is the direct test of `maybe_aclosing`'s no-`aclose()`
branch (`execution.py:57-68`).** The 98% gate could fail on that branch.
-> `tests/test_of.py:77` (`Stream(AsyncIteratorImpl(5))`) reaches the same
branch through the source path, so it is very likely still covered. This is to
be *verified* with a coverage run during apply, not assumed; if the branch drops
uncovered, the fix is a test on `maybe_aclosing` itself in
`tests/test_execution_model.py` —
testing the helper directly rather than through a public API that no longer
reaches it that way.

**[Churn] 42 call sites across nine test files change.** -> Mechanical:
`.collect(to_generator)` -> `.iterator()`, plus deleting the now-unused import
line. Two sites in `tests/test_collect.py` are deletions rather than rewrites.
The suite is the verification; nothing about the asserted values changes, since
the two expressions were already the same generator.

**[Docs] `to_generator` is in the README quickstart — the first code a reader of
this project sees.** -> This is an improvement, not a cost: the quickstart loses
an import line and gains the Java-parity spelling. But it means the change is
not invisible to newcomers, and the Migration entry has to be explicit that the
replacement is `iterator()` rather than something with `collect` in it.

**[Reversibility] Restoring `to_generator` later would mean restoring
`StreamingCollector`, the `collect()` branch, and the exception in six specs.**
-> Accepted. Nothing in the archive suggests a second `StreamingCollector` was
ever planned, and if a genuinely non-identity streaming collector is wanted
later (a `windowing()`, say), it would be designed against the pipeline as it
then is rather than fitted to a type kept alive for it. Keeping an abstraction
warm for a hypothetical second instance is the cost this change is paying down.

## Migration Plan

One commit, no phases — the break is at import time and there is no partial
state to be in.

1. `src/` deletion first (`collector.py`, then `stream.py`), so the tests fail
   loudly and the 42 call sites are found by the failure rather than by grep.
2. Tests, then README and CLAUDE.md, then the README Migration entry — same
   commit, per the project's rule that every breaking change carries its entry.
3. Roadmap: `to-generator-as-a-factory` is edited in place, not closed. It stays
   queued until this change's tasks are done; its `gate` is restated as this
   change, and it records that the analysis inverted its own proposed fix.

Rollback is `git revert`: nothing persists, nothing migrates, and no on-disk or
wire format is involved.
