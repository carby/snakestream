## Context

See `proposal.md` — Why. The state that shapes the approach: the floor is
`>=3.10`, CI matrices both list 3.10–3.14, and exactly one line in `src/`
(`stream.py:353`) branches on interpreter version. Nothing else in the package
is version-conditional — verified by `grep -rn "version_info" src/`, which
returns that one hit.

Two constraints from the repo, both from `CLAUDE.md`:

- CI gates on `ruff check`, `ruff format --check`, `pytest`, `ty check src` and
  `--cov-fail-under=98`, the last three only on the newest leg. Nothing about
  which leg is newest changes here — 3.14 stays newest — so the conditionals in
  `check.yml` that name `'3.14'` are untouched.
- Every breaking change gets a README Migration entry in the same commit.

One repo constraint from `openspec/specs/lint-rule-selection/spec.md`: a
suppression must name its rule and state a reason. That spec is not modified —
this change *removes* a suppression, which the spec has nothing to say about.

## Goals / Non-Goals

**Goals:**

- Make 3.11 the floor everywhere it is stated, in one commit, with the code the
  floor unlocks deleted in that same commit rather than left for a follow-up.
- Leave the four-step sequence legible: someone reading this change should be
  able to see it is step one of four and what the four are for.

**Non-Goals:**

- Anything about free-threading, `spliterator()`, or the racing executor. The
  destination is the *motivation* for the sequence, recorded in `proposal.md`,
  and no line of this change moves toward it beyond raising the floor. No
  roadmap item is claimed, retired, or re-bucketed.
- The remaining three floor raises. Each is its own change; nothing here
  pre-commits their content beyond the ordering.
- `.readthedocs.yml`, which pins `python: "3.13"`. That is a docs-build
  interpreter, it satisfies `>=3.11`, and it becomes actionable only at the
  3.14 step. Deliberately left alone.
- Any change to what `close()` does on a supported interpreter.

## Decisions

**1. One minor version per change, not one change to 3.14.**

The alternative — a single `raise-python-floor-to-314` — was considered and
rejected on reviewability. The four bumps unlock four *different* and unrelated
lint families (`UP036`+`RUF100` here, `UP046`/PEP 695 generics at 3.12,
`UP043` at 3.13, `UP037`/PEP 649 at 3.14), and the last two rewrite annotations
across most of `src/`. Batched, the diff would be ~40 mechanical rewrites in
which the one behavioural deletion — `close()`'s version fork — would be
invisible. Split, each change has one theme and each commit is separately
revertible, which matters because the floor raises are the cheap part and any
one of them could turn out to be premature.

The cost of the split is four near-identical CI-matrix edits. Accepted.

**2. Delete the version fork rather than keep it as defensive code.**

`if sys.version_info >= (3, 11)` guarding `add_note()` becomes statically true.
Keeping it would mean an untestable false arm, which the coverage gate has to
either reach or ignore. Deleting it is also what `UP036` asks for once
`target-version = "py311"` is set, so keeping it means carrying a suppression
for a branch nobody can execute.

*Alternative considered*: keep the fork and add `# pragma: no cover`. Rejected —
it preserves dead code to satisfy a tool, and the spec now states note
attachment unconditionally, so the fork would contradict the spec it implements.

**3. Split the `close()` spec requirement rather than modify it.**

The `stream-close-handling` spec's `close()` requirement had to lose one
scenario ("Interpreters without note support are unaffected"). `openspec
validate` refuses that: a `MODIFIED` requirement must carry every scenario the
main spec has, and a requirement may not be `REMOVED` and `ADDED` under the same
name. So the requirement is removed and re-stated as two:
`close() runs every registered close handler and raises the first failure`, and
`close() preserves later handler failures as notes`.

This is a tooling constraint producing a result worth having anyway. The old
requirement stated two independent contracts — which handlers run and in what
order, versus how their failures are reported — and only the second is touched
by the floor. The `ExceptionGroup` prohibition, three paragraphs of Java-parity
reasoning, belongs to the second and now sits with it.

*The reasoning is preserved, not paraphrased.* The `ExceptionGroup` decision's
recorded ground is Java's `Streams.composeWithExceptions()`, and it stays
verbatim. What changes is its closing clause, which said the decision was "not a
deferral pending the Python 3.10 floor" — that sentence exists to answer an
objection, and once 3.10 is gone the objection has no referent. It is reworded
to say the objection existed and is now spent, rather than deleted, so a reader
who finds the 2026-08-28 roadmap entry does not re-derive it.

**4. Keep the sentence explaining why the `try` is inside the loop.**

`PERF203`'s suppression goes because ruff stops raising the rule on 3.11+
(zero-cost exceptions), which surfaces as `RUF100`. But the comment underneath
it is not only a rule rebuttal: it records that `close()` catches per-iteration
*because the spec requires every handler to run*. That is worth keeping and is
now the whole of the comment, reworded so it explains the code rather than
argues with a linter.

**5. Roadmap gets a note, not a new entry.**

`roadmap.md` line ~1103 records the `ExceptionGroup` decision and says its old
objection had "an expiry date, since 3.10 leaves the matrix in October 2026."
That prediction is now fact and the line is amended to say so. No new roadmap
row is filed: this change is not a code-quality item, and the four-step sequence
is tracked by the changes themselves.

**6. PEP 646 and PEP 681 are checked and declined, not overlooked.**

Both landed in 3.11, so this change is where they would apply if they applied
anywhere. Neither does, and the check is recorded here so it is not re-run.

*PEP 681 (`dataclass_transform`) has no possible site.* It exists so a library
shipping its **own** dataclass-like decorator, base class or metaclass can tell
a type checker that it synthesizes an `__init__`. This package ships none: the
ten dataclasses (nine in `collectors.py`, one in `sink.py`) are stdlib
`@dataclass(slots=True)`, understood natively, and `Collector` is a hand-written
`__slots__` class with an explicit `__init__` — converting it would make it a
plain stdlib dataclass, still not a transform.

*PEP 646 (variadic generics) has exactly one candidate, and it is a bad one.*
`sort.py`'s `_sort_by_segments()` takes `tuple[Segment, ...]`, builds one column
per segment, and orders lexicographically over a heterogeneous tuple of
extracted keys — the shape `TypeVarTuple` was added for. It earns nothing here
for three reasons, in increasing order of how hard they are to work around:

- The key types are erased deliberately. `KeyExtractor` is
  `Callable[[T], Any | Awaitable[Any]]` because a key needs only to be
  comparable against other keys from the same extractor, and nothing downstream
  consumes its type. A `TypeVarTuple` would thread precise types through the
  internals and discard them at both ends.
- The tuple's element types change mid-flight. `_tolerant_column()` rewrites
  keys into `(present, key)` pairs before the passes run, and the mixed lane
  wraps descending columns in `_Descending`. Expressing a per-column type
  transformation needs `Unpack` contortions less readable than `Any`.
- Segment identity is decided at runtime by signature inspection
  (`_is_comparator_arity()` counts positional parameters). A checker cannot
  follow that, so the variadic type would have to be asserted past the very
  discrimination it describes.

The one shape PEP 646 would type correctly is an operation that does not exist:
a `zip`-like op yielding `Stream[tuple[*Ts]]`. Java has no such method, so
adding it would be an expansion of the 1:1 surface — the `__add__` category, a
separate decision — rather than anything this sequence unlocks.

## Risks / Trade-offs

- **A 3.10 user exists and we do not know it.** → `requires-python` makes the
  break loud at install time — `pip` refuses rather than installing something
  that fails at import — and the README Migration entry names it. Accepted on
  the stated grounds that usage is near zero; this is the user's call and it is
  recorded as such.

- **The sequence stalls after step one, leaving the floor at an arbitrary
  3.11.** → Harmless. Every step is independently valid: 3.11 is a coherent
  floor whether or not 3.12 follows, and nothing in this change depends on the
  later ones landing.

- **The free-threading destination turns out not to work, making four floor
  raises wasted.** → The floor raises are not sunk into that bet. They pay for
  themselves in deleted version forks and modernised annotations regardless, and
  the substrate question is explicitly deferred to its own exploration after the
  floor is in place. Worth stating plainly: nothing in this change proves
  free-threading is the right substrate, and step four is the right place to
  test it, not step one.

- **Coverage moves.** → Removing a statically-true branch can only raise the
  measured figure, and the gate is a floor (`--cov-fail-under=98`). Verified by
  running the gate rather than assumed.

- **`ty` behaves differently once it sees a 3.11 floor.** → It infers the
  target from `requires-python`, so narrowing that could in principle change
  inference. Checked by running `uv run ty check src`, which is what CI runs on
  the 3.14 leg.

## Migration Plan

Single commit; no staged rollout, no deprecation period for 3.10. The break is
enforced by metadata, so rollback is reverting the commit — a `>=3.10` floor
re-admits the interpreter and the deleted fork comes back with it.

Validate exactly what CI validates, in the order CI runs it: `ruff check .`,
`ruff format --check .`, `pytest`, `ty check src`, `pytest
--cov-fail-under=98`. The local interpreter is 3.14, which is the leg the last
three gate on, so a local pass is the same evidence CI's newest leg produces.
The 3.11 leg cannot be reproduced locally and is left to CI.
