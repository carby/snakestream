## Context

See `proposal.md` — Why. Three constraints shape this.

**The previous change built the mechanism; this one sets its scope.** The
`per-file-ignores` entry added by `builtins-stdlib-and-lint-gate` was written
as a deliberate placeholder — eleven families switched off for `tests/**` so
that the `tests/` question stayed a decision rather than a side effect. That
entry is what this change rewrites.

**The inverse tripwire.** The previous change's rule was that no test file be
touched. Here the test files *are* the diff, so the tripwire has to be
different: the suite must still report **567 passing tests**, and no assertion
may end up weaker than it started. Every rewrite is either the same assertion
in a different form or a strictly stronger one.

**The roadmap's numbers did not survive measurement**, and neither did its
description of the `PT011` sites. Both corrections are recorded in the proposal
and drove the shape below. This is the second batch running where re-measuring
a roadmap figure before planning changed the plan.

## Goals / Non-Goals

**Goals:**
- One selection enforced over `src/` and `tests/` alike, with exactly one named
  exemption.
- Fix the two correctness classes hiding in the style noise: guards that vanish
  under `python -O`, and `raises` blocks that accept the wrong exception.
- Leave `ruff check .` green so CI needs no workflow edit, as before.

**Non-Goals:**
- **Not touching `src/`.** It already passes, and `PT` cannot fire there.
- **Not renaming or restructuring tests.** No test is split, merged, renamed or
  re-parametrized beyond what a named rule requires.
- **Not weakening a single assertion to satisfy a rule.** Where a rule and a
  test's purpose genuinely conflict, the rule is suppressed at that line with
  its reason — the mechanism the `lint-rule-selection` capability already
  requires. Exactly one site needs this (Decision 4).

## Decisions

### 1. `PLR2004` is exempted by rule, for one path

The user's call, taken on the measured split: 218 of 283 findings, every one a
literal in test data or a test assertion. `assert largest == 7` names the
expected value at the point it is asserted; hoisting it to `EXPECTED_LARGEST =
7` moves the interesting number away from the interesting line.

The exemption names **the rule**, not its family — `PLR` keeps `PLR1711` and
the rest live over `tests/`, and `PLR2004` itself stays enforced over `src/`,
where it currently finds nothing and would flag a genuine unexplained constant.
That distinction is worth a spec requirement of its own, since the previous
change's entry did the opposite (eleven whole families), and the difference
between the two is the whole quality of the gate.

*Alternative considered:* drop `PLR2004` from `select` globally. Rejected —
simpler config, but `src/` loses a rule it passes clean today, which is paying
for tests' idiom with the library's coverage.

### 2. `assert False` becomes `pytest.fail()` — for the message, and for not depending on rewriting

Eleven sites, all the same shape:

```python
try:
    await anext(it)
except StopAsyncIteration:
    pass
else:
    assert False
```

**Corrected during apply.** This decision originally claimed that `python -O`
strips these guards outright, making them silently pass. That is wrong for this
suite as configured: pytest rewrites assertions inside test modules at import
time, so `assert False` still fires under `-O`. Measured both ways on the real
interpreter — under default pytest the old shape fails under `-O` as it should;
under `--assert=plain -O` it passes silently while `pytest.fail()` still fails.
pytest itself warns on the boundary: "assertions not in test modules or plugins
will be ignored".

So the fix is not repairing a live bug, and two smaller reasons carry it
instead. First, a bare `assert False` reports **no message** — the site
communicates only through its position in the `else:`, and a failure says
nothing about what did not happen. Each rewrite names it. Second, the guard
stops depending on rewriting being enabled and on the code staying inside a
file pytest rewrites; `pytest.fail()` is an ordinary call and holds in both
cases. That is also `B011`'s own stated rationale.

Measured against the real suite rather than argued. Running the five affected
files with `-O --assert=plain`, before this change: **37 passed**. After: **10
failed, 27 passed**, each failure reading `Failed: stream should be exhausted`.

The 37 were vacuous. These tests advance the stream *inside* their assertions
(`assert await it.__anext__() == 4`), so with assertions stripped the stream is
never consumed; the guard's `try` then succeeds, the `else:` runs, and the old
`assert False` was stripped too, so the test passed having checked nothing. The
rewrite does not make that configuration work -- it is not a supported way to
run this suite -- but it makes it *say so* instead of reporting green. That is
the whole of the improvement, and it is smaller and more specific than the
correctness claim this decision originally made.

`B011` and `PT015` both flag these, which is why the raw count of 65 covers
~54 sites.

### 3. `PT011` gets `match=`, not a narrower type — the roadmap had it backwards

The three sites are `pytest.raises(ValueError)` in `test_exception.py`, and the
`ValueError("boom")` is raised by a **user callback** the test installs, to
prove a user exception propagates out through `map()`/`filter()` sequentially
and in parallel. The roadmap proposed narrowing them to `StreamException`,
which would assert the opposite of the test's purpose: the whole point is that
this exception is *not* one of the library's.

`match="boom"` is the fix that fits — it distinguishes the callback's
`ValueError` from any other `ValueError` the pipeline might raise, which is
exactly `PT011`'s complaint, without changing what is being tested.

### 4. `PT012` is suppressed, with its reason

`test_base_is_not_a_value_error` puts a `try`/`except ValueError` *inside*
`pytest.raises(StreamException)` to demonstrate that `StreamException` does not
derive from `ValueError` — the `except` clause must not match, and
`pytest.raises` catches it instead. `PT012` wants one simple statement in the
block; obeying it would delete the mechanism the test exists to exercise.

This is the change's only inline suppression, and it is exactly the case the
existing "suppressions carry the reason" requirement was written for.

### 5. `PLW1510` takes `check=False`, explicitly

`_check()` in `test_static_typing.py` runs `ty` and hands the
`CompletedProcess` back; every caller asserts on `returncode`. A non-zero exit
is the expected outcome of most of those tests. So the fix is the explicit
`check=False`, which is what the rule actually asks for — it objects to the
argument being *implicit*, not to its value.

### 6. Auto-fix first, then hand-edit

25 of the 65 are safe-fixable (`SIM300`, `RET505`, `PLR1711`). Running
`ruff check tests/ --fix` for those and reviewing the diff is faster and less
error-prone than hand-editing 22 yoda conditions, and it keeps the hand-written
part of the diff to the sites that need judgement. `--unsafe-fixes` is **not**
used: its 24 additional fixes include rewrites to assertions, which is exactly
where this change must not move automatically.

## Risks / Trade-offs

- **A rewrite silently weakens an assertion** → the tripwire is the test count
  (567) plus a read of the diff, and the auto-fix step is restricted to safe
  fixes so nothing in an assertion changes without a human writing it. `SIM300`
  reverses an operand order and cannot change a comparison's truth; `PT018`
  splits a conjunction into separate asserts, which strengthens reporting
  without changing what passes.
- **`pytest.fail()` in an `else:` reads differently than `assert False`** →
  accepted, and it is the point: the message says what did not happen, where
  `assert False` said nothing at all.
- **The exemption list grows over time into the thing it replaced** → the new
  requirement forbids exempting a family, so growth is visible one named rule
  at a time, each with a reason. That is the intended cost model.
- **54 sites of churn across the suite for mostly-style findings** → the user's
  explicit call, taken with the counts in front of them. The two correctness
  classes are the justification; the style fixes ride along because a gate that
  is on for some rules and off for others in the same family is the state this
  change exists to end.

## Open Questions

None. The two that mattered — `PLR2004`'s disposition and whether to fix all 65
— were put to the user with the measured counts before any artifact was
written, and are Decisions 1 and 6's premise.
