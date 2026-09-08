## Context

See `proposal.md` — Why. The state that shapes the approach, and is not obvious
from the item in `roadmap/items/stream-of-arity-semantics.md`:

- `Stream.of()`'s single-argument branch is `return Stream(args[0])` — literally
  the constructor call, character for character. The spreading form is not a
  separate mechanism; it is a delegation.
- `Stream(source)` is already public. It is the only name `snakestream/__init__.py`
  exports, it is what README's headline Features bullet describes ("Create a
  stream from a List, Generator, AsyncGenerator, Iterator, AsyncIterator or just
  an object"), and README documents it nowhere.
- Of 1,112 `Stream.of(` occurrences outside the archive, **every one sits on a
  single line**. None spans a line break.

## Goals / Non-Goals

**Goals:**

- Delete the arity dependence rather than relocate it.
- Keep the migration mechanical wherever it can be, and isolate the sites where it
  cannot into a list small enough to check by hand.
- Leave `stream-construction`'s scenarios testing what they claim to test after the
  split, rather than passing vacuously.

**Non-Goals:**

- Any change to normalization, the scalar set, or `Stream.__init__`'s signature.
- Any typing work (see Decision 5).
- Any new name. Nothing is added.

## Decisions

### 1. The migration target is the constructor, because nothing else can be

The obvious alternative is spreading at the call site — `Stream.of(*[1, 2, 3])` —
which is exactly what README's 0.3.5 Migration entries told callers to do when
`str`/`bytes`/`bytearray` joined the scalar set. It cannot work here:

    Stream.of(*gen)  ->  Python drains gen eagerly at the call site
                     ->  Stream.iterate() builds an infinite generator
                     ->  never returns

So a non-spreading source entry point must remain reachable no matter what, and
`Stream(source)` is it. This is also why `iterate()` is rebuilt off the
constructor rather than off `of()`: it is not a stylistic preference, it is the
only form that terminates.

**Alternatives considered.** A new static (`Stream.from_source`, `Stream.of_iterable`)
was rejected: it re-adds under a new spelling the free function deleted in 0.3.0
(`stream_of()` removed "for getting closer to the java api", per README's own
Migration log), and invents a name with no Java counterpart when an existing
public one already does the job.

### 2. The sweep is mechanical because the two calls are today the same call

`Stream.of(X)` -> `Stream(X)` is **behaviour-preserving by construction** for every
single-argument site, whatever `X` is, because that is what `of` does today. There
is no classification step and no per-site judgement: 1,084 one-argument sites, all
single-line, rewritable by regex, with the test suite as the check.

The 28 remaining sites (18 zero-argument, 10 multi-argument) are unaffected by the
semantics and are left alone.

### 3. The scalar-set sites are excluded because sweeping them is vacuous, not because it is wrong

This is the decision that inverts the obvious reading. Sweeping
`Stream.of("abc")` -> `Stream("abc")` is harmless in the sense of preserving
behaviour. The hazard runs the other way: **leaving those sites on `of()` is
harmless too, and that is the problem.**

After the split the two forms diverge on iterables and agree on the scalar set:

| argument | `Stream.of(x)` | `Stream(x)` |
|---|---|---|
| `[1, 2]` | 1 element (the list) | 2 elements |
| a generator | 1 element (the object) | its yields |
| `"abc"` | 1 element | 1 element |
| `b"ab"` / `bytearray` / `memoryview` | 1 element | 1 element |
| `{"a": 1}` | 1 element | 1 element |
| `None` / `1` | 1 element | 1 element |

They agree on the scalar set **because `of` is atomic by construction**, not
because normalization did anything. So
`assert await Stream.of("abc").collect(to_list()) == ["abc"]` passes after this
change even if `str` were deleted from the scalar set entirely. Nine tests in
`tests/test_of.py` become tautologies that way, and they are the guards on
`define-and-guard-stream-sources` — including the `bytearray`/`memoryview` entry
that README marks as a **silent** break, where the test is the only thing
standing between that decision and a quiet regression.

Hence: the scalar-set scenarios move to `Stream(...)`, and the delta spec says
why in the requirement text so a later reader does not sweep them back.

There are 22 such sites, and they land exactly in the four files that define the
behaviour: `tests/test_of.py` (9), `openspec/specs/stream-construction/spec.md` (7),
`README.md` (3), `roadmap/decisions.md` (3).

### 4. Three groups are excluded from the sweep entirely

- `roadmap/decisions.md` — append-only history.
- `README.md` under `## Migration` (6 sites) — these describe breaks that were
  genuinely made *against `Stream.of`*. Rewriting them to `Stream(...)` would
  falsify the record of what changed and when.
- `openspec/changes/archive/**`.

A blanket regex over the tree would hit all three. The sweep needs a denylist,
not just a pattern.

### 5. Typing is neutral, and the spec that says otherwise is a pre-existing defect

`generic-stream-typing`'s first scenario claims `Stream.of([1, 2, 3])` infers
`int`. Checked under `ty`:

    Stream.of([1, 2, 3])  ->  Stream[Unknown]
    Stream([1, 2, 3])     ->  Stream[Unknown]
    Stream.of(1, 2, 3)    ->  Stream[Unknown]

All three, today. So the migration costs nothing statically and there is no
typing work in scope. That the scenario is aspirational is recorded here and
left alone — it predates this change and is not caused by it.

### 6. The constructor is documented as a Python-native entry point, not as a parity row

`of()`'s README row currently carries ~8 lines of "diverges from Java". After the
change it becomes a match, and the Python-native part — normalization — has to be
documented somewhere. It is documented in **prose**, before the parity tables, on
the precedent README already set one section earlier for the dunders ("Python's
dunder methods are not Java methods — so they live here rather than becoming rows
nobody wrote"), and alongside `__add__`, which CLAUDE.md already names as the one
member with no Java counterpart.

**`StreamSupport` was considered as a parity home and rejected on three checks:**

1. *Is there a totality defect to repair?* No. README's tables claim totality over
   `Stream`, `BaseStream`, `Collectors` and `Comparator` — four types, named.
   `StreamSupport` is out of scope by declaration. No row is missing.
2. *Is the wholesale skip wrong about it?* Only partly. `StreamSupport` has eight
   statics; six are primitive specializations that the stated autoboxing reason
   genuinely covers. Only the two generic `stream(...)` overloads borrow a reason
   that does not fit — a wording fix, not a hole to move into.
3. *Is `Stream(source)` actually `StreamSupport.stream()`?* No, and this is
   decisive. Java's takes a `Spliterator` plus a parallel flag. `Stream(source)`
   takes anything at all and does not accept a `Spliterator`; the parallel flag is
   `.parallel()`, a separate axis. Claiming the row would be a parity claim that is
   not true.

The real counterparts of `Stream([1, 2, 3])` are `Collection.stream()` and
`Arrays.stream(T[])` — methods on types snakestream does not have and the tables
do not cover. **The normalizing constructor has no Java counterpart in scope on any
of the four types.** That is precisely why it has been hiding inside `of()`'s row:
the spreading form was the only documented way to reach a feature with nowhere to
be documented. This change stops concealing a pre-existing documentation gap; it
does not create one.

### 7. Only `stream-construction` gets a delta; the other 24 specs are swept in place

122 `Stream.of([...])` occurrences across 24 further live specs are **illustrative
examples inside scenarios whose requirements do not change**. A delta records a
requirement change, and these have none. They are corrected directly in
`openspec/specs/**` as a mechanical implementation task.

**Alternative considered:** a delta per capability, which is protocol-pure — no
live spec edited outside a delta — but forces `MODIFIED Requirements` to carry 24
entire requirement blocks copied verbatim, which is exactly the shape the specs
instruction warns silently loses detail at archive time. The risk of that fan-out
exceeds the risk of an in-place example correction that changes no normative text.

## Risks / Trade-offs

- **A silent break.** `Stream.of(some_list)` changes from N elements to 1, and
  nothing raises. → Unavoidable given the decision; mitigated by a README Migration
  entry stating it is silent (the log already carries three such entries and the
  convention for them), and by the migration being a single mechanical substitution
  callers can apply tree-wide.
- **A regex sweep touching prose it must not.** → The denylist in Decision 4, applied
  as an explicit path exclusion rather than trusted to reviewer attention.
- **The nine scalar tests silently going vacuous.** → Decision 3, plus requirement
  text in the delta spec recording *why* they are stated against `Stream(...)`, so
  the next reader does not helpfully sweep them back.
- **Three README passages that argue *from* `Stream.of()` being the source entry
  point** (the `generate()` section, `generate()`'s parity row, `ordered()`'s parity
  row). Substitution fixes all three, but a missed one leaves a parity table
  defending itself with a sentence that no longer matches the code — the same
  pathology `roadmap/items/sink-sentinel-placement.md` exists to fix. → Enumerated
  as named tasks rather than left to the sweep.
- **Scope.** `Stream.__init__(self, source, close_handlers=None)` exposes internal
  plumbing as its second positional parameter, and this change makes the constructor
  the documented idiom. → Deliberately left untouched: the change already carries one
  silent break, and adding a second (loud) one plus its Migration entry to the same
  commit buys nothing this change needs. If the parameter should be keyword-only,
  that is its own item with its own argument.

## Migration Plan

One commit, per the roadmap item's gate — the break lands whole or not at all:
`of()` atomic, `iterate()` rebuilt, every call site swept, README Migration entry.
A partial landing leaves the tree with two meanings of `Stream.of()` in circulation
and is worse than either end state.

Rollback is a revert; there is no data or persisted state involved.
