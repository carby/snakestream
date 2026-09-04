## Context

See `proposal.md` — Why, and the two archived predecessors for the sequence.

This step is small, and the design work is almost entirely in what it *declines*.
The mechanical half is 14 ruff-autofixable `UP043` findings and three
one-line version edits; the useful half is two 3.13 typing features checked
against real call sites and turned down, with the evidence recorded so neither
question has to be re-derived.

State that shapes it:

- `Collector[T, A, R]` is annotated at 45 sites across `src/`. Counting the
  shapes: `A` is written `Any` at **28** of them, making the middle parameter
  noise at the majority of use sites. `R` is `Any` at 13, and is otherwise a
  real type (`dict[R, Any]`, `T | None`, `float`, `SummaryStatistics`, `M`).
- `is_async_callable()` (`callable_dispatch.py`) is the package's single
  classification predicate, applied to mappers, predicates, comparators,
  consumers, key extractors and accumulators alike — declared
  `(fn: Callable) -> bool`.
- Around 30 `cast("Awaitable[…]", …)` calls exist, nearly all in the shape
  documented as the *canonical shape* in `callable_dispatch.py`: classify once
  into a hoisted `is_async` local or `AsyncDispatch` attribute, then per element
  do `r = fn(x)` and `if is_async: r = await cast(...)`.

## Goals / Non-Goals

**Goals:**

- Move the floor to 3.13 and take the one thing 3.13 gives for free.
- Record the two declines with enough evidence that they read as decisions.

**Non-Goals:**

- Reducing the `cast()` count. That is a separate question with a separate
  answer (decision 3), and this change does not open it.
- Changing `Collector`'s parameter list in any way.
- `.readthedocs.yml`'s `python: "3.13"` pin — it now sits exactly *at* the
  floor rather than above it, which is worth noticing but still needs no edit.
  It becomes actionable at the 3.14 step.

## Decisions

**1. Take `UP043` via `ruff --fix`, and verify rather than trust it.**

All 14 findings are autofixable and each removes an explicit `None` that PEP 696
now supplies as a default, so before and after denote the identical type. This
is the one place in the four-step sequence where the autofixer should simply be
run. What is *not* delegated is the check: `ty check src` and the four
`tests/typing/` fixtures both run afterwards, because "denotes the identical
type" is a claim about typeshed's defaults, not something the diff shows.

**2. PEP 696 defaults are declined on `Collector` — the parameter that wants one
cannot have one.**

The observation that suggests defaults is real: `A` is `Any` at 28 of 45 sites,
so most annotations carry a placeholder in the middle. But PEP 696 requires
defaults to be *trailing*, exactly as function parameter defaults are. In
`Collector[T, A, R]` that permits a default on `R` alone — and `R` is the
parameter that is almost always a real type. The default would be available
precisely where it is not wanted.

Reaching `A` would mean reordering to `Collector[T, R, A = Any]`. That is
rejected outright: it is a **silent** break at type level. Every existing
`Collector[T, Any, R]` annotation would keep type-checking while meaning
something new (`A` becoming `Any`, `R` becoming what was `A`), which is the
worst available failure mode — no error at the call site, wrong types
downstream. Weighed against saving one token at 28 sites, it is not close.

*Alternative considered — default `R = A`, so a finisher-less collector could be
written `Collector[Any, C]`.* Rejected: it applies at four sites, and it makes
`Collector[T, Any]` read as an annotation someone forgot to finish rather than
one that means `Collector[T, Any, Any]`. A default should make the common case
shorter without making it ambiguous; this one fails the second half.

**3. PEP 742 `TypeIs` is declined on `is_async_callable()` — and the reason is
the library's central performance decision.**

`TypeIs` narrows a value at the point a predicate is *called*. The library
deliberately does not call its predicate at the point of use. The
`callable-dispatch` spec and `callable_dispatch.py`'s canonical-shape comment
both require classification to happen **once per composition**, hoisted into a
local or an `AsyncDispatch` attribute, with the per-element path reading a plain
`bool`. That hoist is the optimisation; the `cast()` is its cost.

Verified rather than reasoned about. A probe under the `ty` version CI uses:

- The call-site shape narrows correctly. `if is_async_cmp(fn): await fn(a, b)`
  type-checks with no cast, so `TypeIs` does work in principle.
- The hoisted shape does not, and cannot. `is_async = is_async_cmp(fn)` followed
  by `if is_async: await r` inside a loop reports
  `error[invalid-await]: 'int | Awaitable[int]' is not awaitable`. No narrowing
  survives a stored boolean, because a `bool` carries no relationship to the
  value it was derived from.

A second, independent blocker: `is_async_callable` is polymorphic over callable
kinds. `TypeIs[X]` names one concrete `X`, so adopting it would mean splitting
one predicate into per-kind predicates — `is_async_comparator`,
`is_async_mapper`, and so on — multiplying the package's single classification
point into a family of near-identical ones. Either blocker alone is sufficient.

*This is consistent with a decision already on the record and should be read
alongside it.* `roadmap.md` (~line 2015) documents the `AsyncComparator` casts
at `sort()`'s two reroute sites as deliberate and user-approved — placed "where
`is_async_callable` or the trial comparison has just *proved* the narrowing" —
and records that a `cast("Awaitable[int]", …)` inside `_merge`'s loop was
*rejected*, on the ground that it states the narrowing at the least informative
point and puts a cast on the per-comparison path. Those two sites are the ones
`TypeIs` could plausibly reach, and they are already the considered position.
Nothing here re-opens them.

**4. Respell the `stream-iterator` spec, and say in the spec why.**

`AsyncGenerator[T, None]` and `AsyncGenerator[T]` denote the same type, so the
spec was not wrong and this delta changes no requirement. It is taken so the
spec and the code read alike, and the delta carries one sentence saying the
shorter form is the same contract rather than a relaxed one — because a reader
meeting `AsyncGenerator[T]` in a spec could otherwise reasonably wonder whether
the send type had been left unspecified on purpose.

## Risks / Trade-offs

- **`ruff --fix` rewrites something beyond the 14 findings.** → Run it with
  `--select=UP043` rather than bare, and read the diff. Fourteen edits, each one
  line; anything else in the diff is a bug in the invocation.

- **Typeshed's `AsyncGenerator` default differs from what is assumed here.** →
  Not assumed: `ty check src` and the four `tests/typing/` fixtures run after
  the fix, and the two negative fixtures must still fail. A default that did not
  actually exist would surface as an error, not silence.

- **The two declines get re-proposed later as "obvious cleanups".** → The
  mitigation is this document plus `roadmap.md`'s existing entry. Both declines
  name their blocker concretely — trailing-only defaults, and narrowing through
  a stored `bool` — so a future proposal has to answer the blocker rather than
  restate the appeal.

- **`.readthedocs.yml` now pins exactly the floor.** → Harmless today, and it
  will need an edit one step from now. Flagged in Non-Goals so step four
  inherits it rather than rediscovering it.

## Migration Plan

Single commit; rollback is reverting it. The interpreter break is enforced by
metadata and is loud at install time. No runtime or typing behaviour changes, so
there is nothing to stage or feature-flag.

Validate exactly what CI validates, in order: `ruff check .`,
`ruff format --check .`, `pytest`, `ty check src`, `pytest --cov-fail-under=98`.
The local interpreter is 3.14; the 3.13 leg is left to CI.
