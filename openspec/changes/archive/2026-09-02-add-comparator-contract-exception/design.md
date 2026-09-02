## Context

See proposal.md — Why. The state this design starts from, established by the
commit immediately preceding it (`refactor(comparator): inline the
comparator-result type check`): the check is written out at six sites, sharing
only a message constant from `exception.py`, and each site reads

```python
if type(sign) is not int:
    raise TypeError(COMPARATOR_RESULT_TYPE_MESSAGE.format(type(sign).__name__))
```

That shape is what makes this change mechanical: there is no helper to route
through, so the exception type is named at the raise and nowhere else.

Two existing constraints bound the solution. `comparator-contract` requires
`TypeError`, asserted by eight `pytest.raises(TypeError)` tests. And
`exception-hierarchy` requires `StreamException` to derive from `Exception`
and nothing else, with a stated reason — a stream-reuse error is not a
`ValueError` — that is about the *base*, not about leaves.

## Goals / Non-Goals

**Goals:**

- `except StreamException` catches every exception the library raises, with no
  remaining escapee.
- The two comparator-contract violations raised inside
  `_checked_segment_comparator` — an async segment, and a non-`int` result —
  are catchable together.
- Existing `except TypeError` call sites are unaffected, provably.

**Non-Goals:**

- Changing when, where, or on which value the check fires. Control flow,
  message, and conditions are untouched.
- Exporting anything from `snakestream/__init__.py`. Exceptions live in
  `snakestream.exception` and are imported from there, as the two existing
  leaves are.
- Revisiting whether the async-comparator rejection should also get a named
  leaf. It already sits inside the hierarchy as a `StreamBuildException`; a
  name for it is separable and not needed to close this gap.

## Decisions

### Decision 1: A new leaf, not a reuse of `StreamBuildException`

Raising a bare `StreamBuildException` at the six sites would close the
hierarchy gap in one line each and add no new public name — but it would break
every `except TypeError` call site, and `comparator-contract` mandates that
type. Rejected on compatibility alone.

The alternative of leaving the bare `TypeError` and instead *weakening*
`exception-hierarchy`'s purpose statement to "every exception the library
defines" was considered and rejected: the requirement is already worded that
way, and the wording is what lets the gap persist. The Purpose section states
the intent the wording fails to deliver, and the intent is the part worth
keeping.

### Decision 2: Base it on `StreamBuildException`, not `StreamException`

`ComparatorContractException(StreamBuildException, TypeError)` rather than
`(StreamException, TypeError)`.

The argument is the adjacency in `_checked_segment_comparator`: an async
comparator segment raises `StreamBuildException` two lines above a non-`int`
result raising this. Both mean "the comparator you supplied cannot be used".
A caller who wants to handle one almost certainly wants to handle the other,
and basing on `StreamException` would force them to name both.

The objection is that this is detected mid-sort, not at build time. It does
not hold: `StreamBuildException` is *already* raised mid-sort at that same
site, because a comparator's shape can only be discovered by invoking it.
"Build" describes the fault — something wrong with how the pipeline was
constructed — not the moment it surfaces.

### Decision 3: Mix in `TypeError` on the leaf, and say so in the spec

MRO verified valid:

```
ComparatorContractException -> StreamBuildException -> StreamException
                            -> TypeError -> Exception -> BaseException -> object
```

`except TypeError`, `except StreamBuildException`, `except StreamException`
and `except Exception` all catch it; `except ValueError` does not.

`exception-hierarchy` says the base "SHALL NOT derive from any built-in
exception other than `Exception`". A leaf mixing in `TypeError` does not
violate that sentence, but a reader could reasonably think it contradicts its
spirit, so the delta states the leaf rule explicitly rather than leaving it to
inference. The distinction that makes both coherent: the base must stay narrow
because it is a catch-all and widening it would sweep in unrelated built-ins;
a leaf may be specific because it describes exactly one fault, and here that
fault genuinely *is* a type error.

### Decision 4: Name it `ComparatorContractException`

Follows the `*Exception` suffix both existing leaves use, and names the spec
it enforces (`comparator-contract`). Java has no counterpart to borrow —
`Comparator<T>` is statically typed there, so the failure cannot arise — which
is why this is the one exception name in the library not taken from Java.
`ComparatorResultTypeError` was the alternative; rejected for breaking the
suffix convention, and because "result type" describes the check while
"contract" describes the rule.

### Decision 5: The exception owns its message, and takes the value

Each site says `raise ComparatorContractException(sign)`; the class formats.
The preceding commit's exported `COMPARATOR_RESULT_TYPE_MESSAGE` becomes a
module-private `_RESULT_TYPE_MESSAGE`, because a public name for the message
only earned its keep while there was no class to attach it to. Six sites can
no longer word the rejection differently from one another, and the import at
each shrinks from two names to one.

The value is kept in `args` and rendered in `__str__` rather than formatted in
`__init__`. `BaseException.__reduce__` replays `args` through `__init__`, so an
instance constructed from a finished message comes back from a round trip
reporting the type of the *message*: `not bool` becomes `not str`. Verified
both ways before choosing. Nothing in this library pickles — `PROCESSES` is a
worker count, there is no `multiprocessing` — so this is a latent wart rather
than a live bug, but it costs one `__str__` to not have.

## Risks / Trade-offs

- **A caller matching on exact type** (`type(e) is TypeError`, or
  `except TypeError` followed by re-raising anything not exactly `TypeError`)
  changes behavior → Not mitigated, and not worth mitigating: exact-type
  matching on built-in exceptions is rare and already fragile. The library has
  never promised the exact class, only that `except TypeError` catches. Called
  out in the README Migration entry so it is discoverable.

- **The new name widens the public surface**, and a public exception type is
  hard to withdraw later → Accepted. It is one name in a module that already
  exists to hold exactly these, and the hierarchy is the reason it is public
  at all.

- **`ty` may narrow differently** now that the raised type is a library class
  rather than a built-in, in the same way inlining the raise let it drop three
  `cast("int", sign)` calls → Low, and self-revealing: the type checker runs in
  CI on the 3.14 leg and either accepts the narrowing or reports it. Verify
  during implementation rather than predicting.

## Migration Plan

None required — the change is purely widening, so there is nothing for a
caller to migrate. The README Migration entry is marked `(not breaking)`,
following the precedent of the `StreamException` base entry at README.md:295,
and exists so the added catchability is discoverable rather than because
action is needed.

Rollback is a single revert: no data, no persisted state, no interface a
downstream can have come to depend on within one release.
