+++
id = "implement-python-data-model"
title = "`Stream` implements Python's data model (`implement-python-data-model`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "implement-python-data-model"
+++

**`implement-python-data-model`** (2026-08-31) — `Stream` implemented **no**
dunder methods at all, so the library's own guiding principle, Java's surface
with Python underneath, was unmet at exactly the place Python shows through.
Adds `__aiter__`, `__enter__`/`__exit__` and `__repr__` as **parity** — Java's
stream satisfies its language's iteration, resource and `toString` protocols
and ours satisfied none of Python's equivalents — plus `__add__` over
`Stream.concat` as the one **deliberate expansion**, argued as an exception
rather than smuggled in with the others. Third of question 7's three.

**`__bool__` raising is the member that justified the change existing.**
`bool(Stream.empty())` was `True`, not because anyone decided it but because
`object.__bool__` is the default and nobody overrode it, so `if stream:`
answered a question the caller plainly meant to ask, answered it wrong, and
said nothing. There is no correct synchronous answer to give instead, so
refusing is the fix — the one operation this library declines that Python
permits on every other object. The message names `count()`, `any_match()` and
`find_any()`, because a `TypeError` that only says no leaves the caller no
better off than the wrong `True` did.

**The `__getitem__` finding is the one worth not rediscovering.** It is the
only refused protocol that could have worked — `s[10:20]` is lazy and returns
a `Stream` — and it is excluded on a mechanical hazard verified on 3.14:
Python synthesizes an iterator from `__getitem__` when `__iter__` is absent,
so defining it would make `for x in stream` call `stream[0]`, receive a
`Stream`, and loop forever without ever raising. It cannot be added alone;
`__iter__` defined-to-raise must land in the same change, never after. All six
refusals are now **specified rather than merely absent**, which is the same
failure mode question 5 found in README's parity tables: absence that no
artifact could express reads as an oversight rather than a decision.

`async with` was split off and parked in **Later** — `CloseHandler` is a sync
no-arg callable and `close()` never awaits, so `with` is the honest protocol
for the contract as it stands, and the async pair would be a claim about
`stream-close-handling` rather than about two methods.
