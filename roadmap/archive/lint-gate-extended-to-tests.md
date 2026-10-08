+++
id = "lint-gate-extended-to-tests"
title = "The lint gate extended to `tests/`"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**The lint gate extended to `tests/`** (2026-08-26). Both **Next** items at
once, because they were one edit: `PT011` could not be fixed without enabling
`PT`, which was the `tests/` question.
`openspec/changes/extend-lint-gate-to-tests`.

**Both of this roadmap's figures for the item were wrong, and measuring
before planning changed the change.** The recorded **61** was a trial set
that omitted `PLR`, `PLW`, `RET`, `PIE` and `FURB`; the real total under the
selection actually in `pyproject.toml`, plus `PT`, was **283**. Of those,
**218 were `PLR2004`** alone — magic-value-comparison, firing on
`lambda x: x > 5` and `assert largest == 7`, which in a test is the data and
the expected value. Exempted for `tests/` and only there, by **rule and not
by family**, so the rest of `PLR` still applies to tests and `PLR2004` still
applies to `src/`. That distinction earned a spec requirement of its own: the
previous change's entry switched off eleven whole families, and the
difference between the two is the whole quality of the gate. The remaining
**65** findings (~54 sites, since `B011` and `PT015` flag the same eleven)
were all fixed; `ruff check .` is now clean over the whole tree.

**The roadmap also had `PT011` backwards, and the correction is the more
useful record.** It described three `pytest.raises(Exception)` sites to be
narrowed to `StreamException` now that story 1 had shipped it. They are
`pytest.raises(ValueError)` in `test_exception.py`, and the
`ValueError("boom")` is raised by a **user callback** the test installs, to
prove a user exception propagates out through `map()`/`filter()` sequentially
and in parallel. Naming a library base would have asserted the opposite of
the test's purpose. `match="boom"` was the fix that fits.

**The `assert False` claim needed correcting too, mid-apply.** The change was
planned on the premise that `python -O` strips those eleven guards outright,
making them silently pass — a live correctness bug. That is false for this
suite: pytest rewrites assertions inside test modules at import time, so
`assert False` fires under `-O` as it should. What the rewrite actually buys
was then measured against a baseline worktree at HEAD, under
`-O --assert=plain`: **before, 37 passed; after, 10 failed** reading
`Failed: stream should be exhausted`. Those 37 were vacuous — these tests
advance the stream *inside* their assertions, so with assertions stripped the
stream is never consumed, the guard's `try` succeeds, and the old
`assert False` in the `else:` was stripped as well. The rewrite does not make
that configuration work; it makes it say so instead of reporting green. Plus
the plain win: `pytest.fail(msg)` names what did not happen where
`assert False` said nothing.

The rest: 22 `SIM300` yoda conditions, 3 `PT006`, 3 `PT018` composite
assertions split so a failure names which half broke, 4 `PLW0108`, 2 `C417`,
2 `RET505`, 1 each of `SIM401`, `PLR1711`, `PLW1510` (explicit `check=False`
— callers assert on `returncode`, so only the implicitness was the finding).
One inline suppression, `PT012` on `test_base_is_not_a_value_error`, where
the `try`/`except ValueError` inside `pytest.raises(StreamException)` is the
mechanism the test exists to demonstrate. 25 of the fixes were taken with
`ruff check --fix`; `--unsafe-fixes` was deliberately not used, since its
extra fixes reach into assertions.

**The tripwire was inverted from the previous change and held.** That one
required no test file be touched; this one is 18 test files and 69 changed
lines, so the rule was the count — **567 passed**, unchanged — plus a read of
every hunk confirming each is the same assertion restated or a strictly
stronger one. No `src/` file was touched, coverage held at 98.04%, `ty` clean.
