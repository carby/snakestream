## Context

See proposal.md — Why for the motivation and the table of 27 names. What
matters here is the shape of the package the rule has to be true of.

`src/snakestream` is ten modules and an `__init__.py` that exports two names.
Callers reach everything else by module path — README's quickstart imports
`to_generator` from `snakestream.collector`, and the archived
`split-collector-protocol-and-factories` change treated moving the factories
out of that module as a breaking import-path change, with a Migration-log
entry, precisely because the path is public. So the package has two kinds of
caller-facing name (`Stream`, `PROCESSES` from the top level; ~40 factories,
exceptions and comparators from module paths) and one kind of internal name,
and the underscore currently correlates with none of the three.

The import graph is small and acyclic enough to be read mechanically: an AST
pass over `from snakestream.X import ...` statements answers "is this name
used outside its module?" exactly. That is what makes story 1 a mechanical
sweep rather than a judgment call, and it is the property the enforcement
check is built on.

Two constraints bound the sweep:

- `Op.__repr__` derives an op's rendered name from its class name
  (`type(self).__name__.removeprefix("_").removesuffix("Op")`). It is already
  tolerant of the underscore's absence, so renaming nine `Op` subclasses
  cannot change `Stream.__repr__`'s output — but `removeprefix("_")` becomes
  dead code the moment no `Op` subclass is underscored.
- `execution.py` binds `RACING = Racing(PROCESSES)` at import. This is what
  makes `PROCESSES` a fact rather than a lever, and it is also why removing
  the export cannot break a working call site: there is no working call site
  that assignment ever affected.

## Goals / Non-Goals

**Goals:**

- One rule, stated once, true of every module-level name in the package.
- The half of the rule that is decidable from the import graph is enforced by
  the build, not by review.
- The sweep is provably scope-limited: definition lines, import lines, use
  sites and docs — no argument, branch, or call-order change anywhere.

**Non-Goals:**

- Deciding, in code, what "documented API" means. The rule's second clause is
  a human judgment (see decision 2) and is applied once, by hand, in story 2.
- Any change to what a caller can do. Story 3 removes an export nobody could
  use for anything; nothing else in the change is caller-visible.
- Reducing the number of modules a caller imports from, or changing which
  module owns which name.

## Decisions

### 1. The public boundary stays "module path", not `__init__.py`

The rule says the underscore is not an API marker. The obvious follow-on is to
make `__init__.py` the API marker instead — re-export the ~40 caller-facing
names from the top level and treat every module path as internal. Considered
and declined.

- **It cannot be enforced.** Python has no mechanism to stop
  `from snakestream.collectors import to_list`. The regulation available is a
  documented surface plus a test that catches drift — and the documented
  surface today is README's parity tables, which already do that job by module
  path.
- **It re-breaks a path broken three weeks ago.** `snakestream.collector` and
  `snakestream.collectors` were split apart on 2026-08-26 with a deliberate
  Java-faithful break and a Migration entry; demoting both paths to internal
  immediately afterwards would spend a second break to reverse the reasoning
  of the first.
- **It buys nothing this change needs.** All 27 renames are internal-to-
  internal or internal-to-caller-facing-module; not one of them becomes
  correct or incorrect depending on where the top-level export list sits.

The rejected third option, renaming internal modules to `_execution.py`,
`_sink.py` and so on, has the same enforcement gap plus a full import-path
break across `tests/`, and would make the file tree — rather than the import
graph — the thing a contributor has to keep consistent.

**Consequence recorded so it is not re-litigated:** a bare module-level name
in this package means "another module uses it", not "callers may use it".
That is stated in the spec's first requirement as a non-promise, because the
absence of the old meaning is the thing most likely to be misread.

### 2. Only one direction of the rule is enforceable; the other is a one-time pass

"Underscored and imported elsewhere" is decidable from the import graph.
"Bare and used only locally" is **not** decidable, because the correct answer
depends on whether callers reach the name: `to_list`, `comparing`,
`StreamException` and `to_generator` are all bare, all correct, and none is
imported by any module in `src/snakestream` — callers import them instead. A
check for the second direction would need a maintained list of caller-facing
names, which is exactly the `__init__.py` surface decision 1 declined.

So the build enforces direction 1 and the spec requires only that. Direction 2
(story 2's eight names) is applied once by hand, and its correctness argument
is per-name: each of `stream_through`, `group_through`, `race_through`,
`feed_through`, `drain`, `Sequential`, `Racing` and `merge_sort` is absent
from README, absent from `__init__.py`, and used only by its own module.

**Alternative considered:** skip story 2 entirely and enforce direction 1
only. Rejected — that is how `sink.py` reached nine bare internal names beside
four underscored ones. A rule that only ever removes underscores leaves the
next reader unable to infer anything from a bare name, and the first thing
they will do is add an underscore to something for the old reason.

### 3. The check is a test, not a lint rule — for now

Ruff ships `PLC2701` (import-private-name), which is exactly this rule.
Rejected for now on three counts, and the reasoning is recorded so it can be
revisited:

- It is **preview-only**, and `preview = true` in `[tool.ruff.lint]` changes
  the behaviour of every selected rule family, not just the one being added.
  This project selects fifteen families; enabling preview to acquire one rule
  buys an unscoped set of new findings across all of them.
- It **skips imports used only in annotations**, by design. `_Aiter` is
  exactly that shape, so the rule would not have reported one of the 27.
- The house pattern for an invariant about the package's own name surface is
  already a test: `tests/test_package_exports.py` asserts the export surface
  by inspecting `dir(snakestream)`.

The test lives in a new `tests/test_name_visibility.py` rather than in
`test_package_exports.py`: that module is about what callers can import from
the package, and this one is about how the package imports from itself.

It reads `ast.ImportFrom` nodes across `src/snakestream/*.py`, keeps those
whose module starts with `snakestream`, and reports any imported name starting
with `_`. It walks the whole tree rather than only module-level statements, so
a function-local import (`stream.py` has one) is covered too. Failure names
importer, definer and name.

**When `PLC2701` stabilises, switch to it and delete the test** — the
`lint-rule-selection` capability already establishes that per-path exemptions
name the individual rule with a recorded reason, which is how `tests/**` would
be exempted.

### 4. What the renamed names become

Twenty-five of the 27 drop the underscore and nothing else. Two get an
argument:

- **`_C` -> `C`, `_M` -> `M`.** Java names these two type parameters exactly
  that: `Collectors.toCollection` takes `<C extends Collection<T>>`,
  `Collectors.toMap`'s map-supplier form takes `<M extends Map<K,U>>`. The
  Java-faithful reading and the rule agree, and `T`, `R`, `A` in the same file
  are already bare. Their bound, `_SupportsAdd`, is used only in `type.py` and
  stays private — which is the rule working as intended within one file.
  - *Alternative:* keep the underscore because typeshed convention underscores
    TypeVars so `import *` does not export them. Rejected: `type.py` already
    has three bare TypeVars, so the convention is not being followed here in
    any case, and nothing in this package uses `import *`.
- **`_UNSET` -> `UNSET`.** This one is also a small correctness win
  independent of the rule: the sentinel is the default of a public factory
  argument (`reducing(identity=_UNSET, ...)`), so its name is already rendered
  to users by `help()` and any generated documentation, wearing a private
  mark.

`_ASYNC_COMPARATOR_MESSAGE` is renamed, **not** moved to `exception.py` beside
`_RESULT_TYPE_MESSAGE`. The reason to move it would be to name the message
once in one place, and it already is named once; the move would relocate a
constant without changing how many modules import it, and `_RESULT_TYPE_MESSAGE`
is module-local to `exception.py`, so it would not even join a cluster.

### 5. `Op.__repr__` loses `removeprefix("_")`

After story 1 no `Op` subclass is underscored, so the call is dead. Deleting
it is in scope because leaving it would preserve, in the one place that reads
class names programmatically, an assumption the change exists to remove — and
because a dead branch there is invisible to coverage (it is a string method,
not a branch). The docstring's `_FlatMapOp -> flat_map` example is updated in
the same edit.

**Trade-off accepted:** an op class added later with an underscore would then
render `_foo` instead of `foo`. That is the correct failure — the name would
be violating the rule, and the check in decision 3 does not catch it (nothing
imports it yet at definition time). The docstring says so.

### 6. `PROCESSES` is removed from two paths, not renamed or deprecated

`snakestream/__init__.py` and `stream.py`'s
`from snakestream.execution import PROCESSES as PROCESSES` both drop it. The
definition in `execution.py` is untouched — the name still exists, still means
what README says it means, and `stream.py` keeps importing `RACING`,
`SEQUENTIAL` and `Executor` from the same statement.

- *Alternative: keep the export and document it as read-only.* Rejected. A
  read-only tuning constant is precisely what `racing-encounter-order` already
  refuses to publish for `_IN_FLIGHT_PER_WORKER`, on the grounds that the
  levers offered for the cost of racing are `unordered()` and `sequential()`.
  Two constants of the same kind cannot get opposite answers in the same test
  file.
- *Alternative: deprecation shim (module `__getattr__` raising a warning).*
  Rejected. Pre-1.0 with little usage, a shim costs a permanent branch in
  `__init__.py` to soften a break for callers who, by the binding-at-import
  argument, were not getting the behaviour they thought they were.

## Risks / Trade-offs

- **A rename sweep touching ten modules hides a real edit.** → Every task
  verifies by `git diff` shape, not by test outcome alone: the claim is that
  each file changes only on definition lines, import lines and use sites. The
  suite must stay green with an unchanged test count, and coverage must not
  move — a rename that changed behaviour would move at least one of the three.
- **A name is renamed at its definition but missed at a use site inside a
  string, docstring or comment.** → `grep` for each old name across `src/`,
  `tests/`, `CLAUDE.md` and `README.md` after the sweep; the expected residue
  is zero. `_UNSET` (30 occurrences in `src/`) and the nine op classes are the
  ones with enough sites to hide one.
- **The new check is written to pass and never tested against a violation.**
  → The spec requires a scenario for the failing direction; the task list
  builds the check by first constructing a violating import in a scratch tree
  (or by asserting on a synthetic module list) and confirming the check reports
  importer, definer and name.
- **Story 2 renames names CLAUDE.md's architecture block prints in a
  diagram.** → Accepted, and the diagram is updated in the same change. The
  five `*_through` verbs are the module's internal vocabulary; the diagram
  reads no worse with underscores, and the alternative is that CLAUDE.md
  documents seven names as though a caller could reach them.
- **`PROCESSES` removal is silent for anyone who was assigning to it.** →
  It cannot be: the name disappears from both import paths, so an assignment
  site fails at import with `ImportError`, not silently. The genuinely silent
  case — a caller who assigned to it and believed it worked — is already
  broken today, and the Migration entry says so explicitly.

## Migration Plan

One commit, no phasing. Stories 1 and 2 are caller-invisible; story 3 is a
single removal that fails loudly at import.

README gains one Migration-log entry covering both dropped paths
(`from snakestream import PROCESSES`, `from snakestream.stream import
PROCESSES`), stating that the constant keeps its name in
`snakestream.execution`, that assigning to it never affected the worker count
because `RACING` binds it at import, and that `.sequential()` / `.unordered()`
remain the supported levers.

`CLAUDE.md` records the rule itself, so the next contributor meets it before
the diff.

Rollback is `git revert`: nothing persists, no data or config shape changes.
