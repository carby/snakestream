## Context

See `proposal.md` — Why. The constraints that shape the approach:

- `Collector` is a concrete class with `__slots__ = ("accumulator", "combiner",
  "finisher", "supplier")`, holding four callables and no per-collection state.
  That statelessness is load-bearing and spec'd: one `Collector` value is safe
  to reuse across streams and across concurrent collections, and
  `collectors.py` relies on it (`_TO_LIST` is one shared value serving every
  group of every `grouping_by()`).
- The import edge runs `collectors` -> `collector` and never back.
  `collector.py` owns the protocol; `collectors.py` owns the ~20 factories.
- The public surface is module-level in `collector.py`/`collectors.py`.
  `snakestream/__init__.py` re-exports only `Stream` and `PROCESSES` — not even
  `Collector` — so nothing here touches it.
- The coverage gate is 98% on the newest interpreter, and this change adds a
  field no execution path reads.

## Goals / Non-Goals

**Goals:**

- Land the vocabulary and the Java-matching declarations so item 1 has
  something to consult, with no behaviour change of its own.
- Keep `Collector` reusable and stateless — the new part must be immutable, or
  the "one value, many collections" guarantee is quietly weakened.

**Non-Goals:**

- Reading the characteristic anywhere. No sink, terminal or executor changes.
- The `IDENTITY_FINISH`/`CONCURRENT` members, and the marking of collectors
  Java leaves unmarked — see `proposal.md` — Non-goals, and the second row of
  the roadmap's item 1 table.

## Decisions

**An `Enum` plus a `frozenset` attribute, not an `IntFlag` bitfield.** Java's
`Collector` carries `Set<Characteristics>` over an enum, and callers read it as
a set. A `Flag` with bitwise `|` would be more compact and arguably more
Pythonic, but the set shape is the observable API and the guiding principle
puts parity on the public surface ahead of internal taste. With one member
today the bitfield's only advantage — cheap combination — has nothing to
combine. `frozenset` rather than `set` because it is immutable: a `Collector`
is shared across concurrent collections, and a mutable characteristics set
would be the type's first piece of mutable shared state.

**Fifth constructor parameter, after `finisher`, defaulting to a shared empty
`frozenset` named at module level.** Appending keeps every existing positional
call valid, which is what makes this non-breaking. The default is a
module-level `_NO_CHARACTERISTICS: frozenset[Characteristics] = frozenset()`
rather than a `frozenset()` call in the signature: ruff's B008 flags calls in
defaults, and naming it at module scope is the same move `collectors.py`
already makes for `_TO_LIST`, for the same reason — it lets the reader rule out
the mutable-default bug without a trip to the docstring. Immutability is what
makes one shared default correct.

**Normalize any iterable to a `frozenset` at construction.** `Collector(...,
characteristics=[Characteristics.UNORDERED])` and `characteristics={...}` both
work and both store a `frozenset`. Rejecting anything but a `frozenset` would
be a needless trap on a parameter most callers will never pass, and normalizing
once at construction keeps every reader downstream free of the question.
`__slots__` gains the name.

**`Characteristics` lives in `collector.py`, beside `Collector`.** It is part
of the protocol, not a factory; putting it in `collectors.py` would invert the
import edge, since `Collector.__init__` needs it for the default. This is the
same placement rule that keeps `to_generator` in `collector.py` beside the
type.

**Derivation is one keyword argument in each of `mapping()` and
`collecting_and_then()`** — `characteristics=downstream.characteristics` on the
`Collector(...)` they already return. No helper, no shared derivation function:
two call sites, one expression each, and a helper would put a name between the
reader and a fact that fits on the line.

**`grouping_by()` and `partitioning_by()` deliberately do not derive**, though
both take a downstream. In Java their characteristics are fixed regardless of
downstream, and the reason is structural rather than incidental: the
downstream's result is a map *value*, and a trait of the values says nothing
about the map. `grouping_by(f, to_set())` builds a `dict` whose insertion order
follows encounter order, so deriving `UNORDERED` from the inner `to_set()`
would be actively wrong. Worth a comment at both sites, because "takes a
downstream, does not derive" reads like an oversight otherwise.

**Testing a declaration nothing consumes.** The scenarios read
`collector.characteristics` directly. That is not a test of an internal — the
attribute *is* the shipped API of this change, and it is what item 1 will read.
Each derivation scenario pairs an ordered and an unordered downstream, so a
hard-coded answer fails.

## Risks / Trade-offs

- **The field is inert until item 1 lands, and an inert field invites
  someone to "finish the job" by marking more factories.** → The
  `collector-to-set` spec pins the declaration to `to_set()` alone, and the
  reason the others are unmarked is written down in both the proposal's
  Non-goals and the roadmap. The pin is a spec, so drift fails validation
  rather than review.
- **Item 1 may want a different shape** — a broader "does this terminal demand
  encounter order?" abstraction that `Collector` merely feeds, rather than
  reading `characteristics` directly. → Matching Java exactly is the mitigation:
  whatever item 1 builds on top, the public part shipped here is the part Java
  has, so it cannot be the wrong thing to have shipped. Nothing here commits
  item 1 to a mechanism.
- **Coverage on a field no execution path reads.** → The spec scenarios read it
  on six collectors (`to_set`, `to_list`, `joining`, and the three derivation
  cases), which covers the constructor path, the default and both derivations.
  No `pragma: no cover` should be needed; if one appears, the field is
  under-specified rather than untestable.
- **Divergence risk in the other direction:** a caller may reasonably expect
  `counting()` to be `UNORDERED` and be surprised it is not. → It is a
  divergence from intuition, not from Java, and it is temporary — item 1
  decides it. Not worth pre-empting on a guess.

## Migration Plan

None. Additive: a new enum, a new defaulted parameter, three factories
declaring what they already were. No rename, no behaviour change, no
migration-log entry. README's parity table gains a row for
`Collector.Characteristics` noting `UNORDERED` implemented and the other two
intentionally deferred, with the reason — the table is where a reader checks
before assuming a Java member is missing.

Rollback is deleting the enum and the parameter; nothing depends on them until
item 1.

## Open Questions

- **Does item 1 read `characteristics` off the `Collector` directly, or does
  `Collector` feed a wider terminal-ordering abstraction that `find_first()`
  and `for_each_ordered()` also implement?** Safely deferred: it changes
  neither these specs, this design, nor the task breakdown — every answer reads
  the same attribute — and item 1 is where the other terminals are in scope.
