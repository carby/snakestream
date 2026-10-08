+++
id = "derive-without-reinit"
title = "`_derive()` copies the next stage instead of re-running `__init__` (`derive-without-reinit`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "derive-without-reinit"
+++

**`derive-without-reinit`** (2026-08-31) — `_derive()` built the next stage
with `type(self)(self._source, self._close_handlers)`, re-entering the user's
constructor: a three-op pipeline plus one mode switch ran it **five times**.
Now derives by `copy.copy`, so a subclass's `__init__` runs once per pipeline
and its state is shared across stages by identity. Question 7 as filed;
second of its three changes. **BREAKING for subclasses only.**

**The item's leak claim was conditional, and the exploration found two larger
problems it had not named.** With `on_close()` registered inside `__init__` —
the idiom CLAUDE.md documents — nothing leaked: `_close_handlers` is passed by
reference, so all five handlers landed in the same list and one `close()`
fired all five. The shared list accidentally masked it. The leak was real only
for a subclass overriding `close()` (measured: 3 opened, 1 closed, 2 orphans).
Either way the **churn** was the defect regardless of the leak — five
connections opened and one used, and perfect cleanup of four resources that
should never have existed is still wrong.

The problem nobody had named is **the signature contract**: passing
`(source, close_handlers)` positionally silently required every subclass to
accept exactly that, with an already-normalized `AsyncGenerator` first. The
natural way to write the documented use case — `DsnStream(dsn)` acquiring a
connection and calling `super().__init__(conn.rows())` — raised `TypeError` on
its first intermediate op, so the documented feature was close to unwritable.
README's own subclassing paragraph described that shape.

**Why copying rather than Java's answer.** Java never had this bug because its
derived stages are an internal type holding no resource and `Stream` is an
interface nobody subclasses. This library went the other way deliberately —
`type(self)` was there to preserve subclass identity across derivation, which
`test_a_user_subclass_survives_a_mode_switch` pins — and once identity is the
requirement, copying is the only way to have it without construction.

**That test could not have caught this**, and is the third instance of the
pattern this file keeps recording: it asserted `seq.resource == "db-handle"`
against a string literal, pinning that the attribute *survived* rather than
that it was the object the constructor assigned, so it passed throughout.
Changing the one assertion to `is` turned it into a reproduction.
