## Context

See `proposal.md` — Why, and the first step's archived change for the sequence.
The state that shapes this one:

- `type.py` declares six module-level `TypeVar`s (`T`, `R`, `A`, `Aiter`, `C`,
  `M`) and ~20 aliases built from them. Eight of the ten modules in
  `src/snakestream` import at least `T`; `execution.py` imports `Aiter`;
  `collectors.py` imports `C` and `M`.
- Four classes use the `Generic[...]` base: `Stream`, `StreamBuilder`, `Sink`,
  `Collector`. These are ruff's four `UP046` findings at `py312`, and the whole
  of what the bump reports.
- The aliases are used **subscripted** throughout (`Predicate[T]`,
  `Mapper[T, R]`, `Comparator[T]`), never bare, so a parameterized `type`
  statement is a faithful translation rather than a widening.
- `FlatMapper = Callable[[T], "Stream[R]"]` is quoted because `Stream` is
  imported under `TYPE_CHECKING` only.

Three things were verified empirically before scoping, not assumed:

1. **`ty` supports PEP 695 fully.** A probe covering `type` statements,
   `class Stream[T]`, method-scoped `def map[R]`, and a bound scoped parameter
   (`def normalize[Aiter: AsyncIterator[Any]]`) type-checked correctly,
   including inferring `Stream[int]` versus `Stream[str]` through a lambda
   passed to `map`. Inference is not degraded by the new syntax.
2. **A `type` statement's RHS is lazy.** `type FlatMapper[T, R] =
   Callable[[T], Stream[R]]` with `Stream` imported only under `TYPE_CHECKING`
   imports and runs at runtime, and `ty check` passes. This is what lets the
   quotes come off at 3.12 instead of waiting for PEP 649 at 3.14.
3. **Runtime introspection changes.** Measured, not predicted:
   `get_origin(Mapper[int, str])` moves from `collections.abc.Callable` to the
   alias object; `get_args` moves from `([int], str | Awaitable[str])` to
   `(int, str)`; the alias itself becomes a `TypeAliasType` whose RHS is behind
   `.__value__`. This is the change's one observable break and the reason it
   gets a Migration entry.

## Goals / Non-Goals

**Goals:**

- Make 3.12 the floor everywhere it is stated, and take PEP 695 where it pays,
  in one commit.
- Leave `type.py` readable as the package's vocabulary. The aliases are the
  thing most modules import; if the conversion makes them harder to read it has
  failed regardless of what ruff says.

**Non-Goals:**

- Full PEP 695 adoption. Free generic functions keep their module-level
  typevars, and methods introducing a new typevar (`Stream.map`'s `R`) are not
  given scoped parameter lists. Decision 2 states why; this is a scope
  boundary chosen deliberately, not work deferred for lack of time.
- Deleting `T`, `R`, `A`, `Aiter`, `C` or `M`. All six survive.
- Anything about free-threading or `spliterator()`. Same non-goal as step one.
- `.readthedocs.yml`'s `python: "3.13"` pin, which still satisfies `>=3.12`
  and becomes actionable only at the 3.14 step.

## Decisions

**1. Convert the four classes and the aliases; stop there.**

The four class conversions are what `UP046` asks for and are unambiguous — each
class's parameters are genuinely class-scoped. The alias conversion is not
demanded by any lint rule (`UP040` does not fire, because the aliases carry no
`TypeAlias` annotation) and is taken anyway, because it is where the payoff is:
it is what unquotes `FlatMapper`, and it is what makes the aliases
self-describing — `type Mapper[T, R] = ...` states its arity in its own line,
where `Mapper = Callable[[T], R | Awaitable[R]]` requires the reader to infer it
from two module-level names declared 20 lines above.

*Alternative considered — classes only, the strict `UP046` reading.* Rejected:
it leaves `class Stream[T]` whose `map()` signature reads
`Mapper[T, R]` with `T` scoped to the class and `R` a module-level `TypeVar`
imported from another file. Two typevar systems in one signature is worse than
either alone, and the diff would be four lines that make the file less coherent.

**2. `Aiter`, `C` and `M` stay `TypeVar`s — and so do `T`, `R`, `A`.**

PEP 695 has no syntax for a *shared, named* type variable. `type` statements
declare aliases, and scoped parameter lists (`class Foo[T]`, `def f[T]`) declare
variables private to one scope. A type variable used by five signatures across
two modules can be expressed only by declaring it five times.

For `C` and `M` that is not merely repetition but repetition *of a bound*:
`M`'s `MutableMapping[Any, Any]` would appear at 5 sites and `C`'s
`_SupportsAdd` at 3, each an independent opportunity to drift. `Aiter`'s bound
carries a four-line comment explaining why it is bound rather than fixed; that
comment has one home today and would have none.

There is also a rule in play. CLAUDE.md's naming rule makes a module-level name
bare **iff** another module uses it — which is exactly why these six are bare.
Inlining them would not satisfy the rule; it would delete the names the rule is
about, and with them the single place each bound is written down. PEP 695's
scoped parameters are the right tool for a variable used once; these are used
across the package, and the older spelling remains the better one for that.

*This is a limitation of PEP 695, stated plainly rather than worked around.*
The aliases convert cleanly because an alias is exactly what a `type` statement
is for. The typevars do not convert cleanly because a shared typevar is not
something PEP 695 models.

**3. `generic-stream-typing` gets no delta, and that is the point.**

Every requirement in that spec is phrased as observable typing behaviour —
"`ty` infers its element type as `int`", "the returned stream is typed as
`Stream[str]`", "`Mapper[T, R]`'s declared return type SHALL be exactly
`R | Awaitable[R]`". None names `Generic`, `TypeVar`, or any mechanism. PEP 695
changes the spelling and leaves every one of those statements true.

So the spec is not edited, and its continuing to hold is the acceptance test for
the conversion. That is already automated: `tests/test_static_typing.py` shells
out to `ty` against four files in `tests/typing/`, two of which must pass
(`good_stream_types.py`, `good_nulls_ordering_types.py`) and two of which must
fail with a specific diagnostic (`bad_stream_map.py` →
`unresolved-attribute`, `bad_to_map_container_without_merge.py`). A PEP 695
conversion that silently widened something to `Any` would break the two
negative files — they stop failing — which is the failure mode most worth
catching and the one a positive-only test suite would miss.

**4. The introspection break gets a Migration entry despite being obscure.**

Nobody is plausibly calling `get_args()` on `snakestream.type.Mapper`. The entry
is written anyway, because the repo's rule is that every breaking change gets
one in the same commit, and because "obscure" is a guess about users rather than
a fact about the API. The entry says plainly that static typing — the surface
these aliases exist for — is unaffected, so a reader can stop after one line.

## Risks / Trade-offs

- **The alias conversion silently widens something to `Any`.** → This is the
  real risk of the change and the reason decision 3 leans on the two *negative*
  typing fixtures: a widening shows up as a test that stops failing, not as one
  that starts. Verified by running `pytest tests/test_static_typing.py` and
  confirming all four still behave as declared.

- **`ty` regresses on PEP 695 in a later version than the one pinned here.** →
  Checked against the `ty` version in the lockfile, which is what CI runs on the
  3.14 leg. Not mitigated beyond that; a dev-dependency bump that broke this
  would break CI loudly rather than silently.

- **Mixed typevar spellings look like an oversight to the next reader.** →
  Genuine and not fully mitigable: after this change `class Stream[T]` coexists
  with a module-level `R`. Decision 2 is the answer, and it is written into
  `type.py` as a comment at the surviving `TypeVar` block so the reason sits
  with the code rather than only in this archive.

- **Four floor raises turn out to be wasted if free-threading is the wrong
  substrate.** → Unchanged from step one, and unchanged in force: this step
  pays for itself in `type.py` alone regardless of what step four concludes.

## Migration Plan

Single commit; rollback is reverting it. `requires-python` makes the
interpreter break loud at install time.

Validate exactly what CI validates, in order: `ruff check .`,
`ruff format --check .`, `pytest`, `ty check src`, `pytest
--cov-fail-under=98`. The local interpreter is 3.14, the leg the last three
gate on. The 3.12 and 3.13 legs are left to CI.

One extra check beyond CI's, because CI would not catch it: confirm
`python -c "from snakestream.type import Mapper; print(Mapper[int, str])"`
still works, i.e. the aliases remain subscriptable at runtime for anyone who
does that.
