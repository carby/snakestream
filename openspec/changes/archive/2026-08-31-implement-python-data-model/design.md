## Context

See proposal.md — Why. `Stream` defines no dunder methods whatsoever today, so
this is not a set of tweaks to existing behaviour but the first pass at the
question "what kind of Python object is a `Stream`?".

The answer is constrained almost entirely by one fact: every terminal operation
is `async def`. Python's data model is overwhelmingly synchronous, so the
protocol set splits cleanly and the split does most of the design work.

```
  lazy — returns a Stream, consumes nothing        │  __add__
  async — Python provides the hook                 │  __aiter__
  lifecycle — no consumption involved              │  __enter__ __exit__ __repr__
  ─────────────────────────────────────────────────┼──────────────────────────
  demands a value synchronously                    │  __len__ __iter__
    → cannot be satisfied at all                   │  __contains__ __eq__
                                                   │  __reversed__ __getitem__
```

## Goals / Non-Goals

**Goals:**

- Satisfy the Python protocols whose Java counterparts `Stream` already claims.
- Close the two synchronous defaults that are silently wrong.
- Leave a record of the refusals, so the absent ones read as decided.

**Non-Goals:**

- `__copy__` — `derive-without-reinit`'s to settle, since that change is what
  makes it load-bearing.
- `__aenter__` / `__aexit__` — parked in the roadmap's **Later**. See below.
- Any change to `stream-iterator` or `stream-close-handling`. The two protocols
  delegate; they do not restate.

## Decisions

### Three of these are parity, one is expansion, and the change says which

The guiding principle is a 1:1 Java API surface with Python exploited underneath.
Dunders are surface, so this change has to justify itself against that principle
rather than under it. The justification differs per member and the proposal splits
them accordingly:

`__aiter__`, `__enter__`/`__exit__` and `__repr__` are **parity**. Java's stream
satisfies its own language's protocols — `BaseStream.iterator()`,
`AutoCloseable` in try-with-resources, `toString()` — and ours satisfies none of
Python's equivalents. The gap is not that Java has a method we lack; it is that
Java's stream is a well-behaved object in its language and ours is not in its own.

`__add__` is **expansion**, and is argued as an exception. `Stream.concat` stays
the contract; the operator delegates and adds nothing. If the principle is ever
tightened, this is the member to reconsider, and it is separable because it is
five lines that call one method.

### `__bool__` raises, and that is the whole point of including it

This is the only place the library refuses an operation Python permits on every
other object, so the reasoning is worth pinning down rather than leaving to the
docstring.

`bool(Stream.empty())` is `True` today. Not because anyone decided it — because
`object.__bool__` is the default and nobody overrode it. `if stream:` therefore
answers a question the caller plainly meant to ask, and answers it wrong, every
time, silently.

*Alternative — return `True` deliberately, documented as "a stream is always
truthy".* Rejected: it is the same wrong answer with a paper trail. The caller
writing `if stream:` means "is there anything in it".

*Alternative — leave it alone.* Rejected on the same grounds, and this is the
member of the set that most justifies the change existing at all: the other four
add convenience, this one removes a silently wrong answer.

The message must name the async alternative. A `TypeError` that only says no
leaves the caller no better off than the wrong `True` did.

### `__getitem__` is excluded for a reason that is not the obvious one

`s[10:20]` is lazy and returns a `Stream`, so it belongs in the first row of the
table above and *could* be implemented. It is excluded on a mechanical hazard,
verified on 3.14: Python's legacy iteration protocol synthesizes an iterator from
`__getitem__` when `__iter__` is absent. Adding slice support would make
`for x in stream` begin to "work" — calling `stream[0]`, receiving a `Stream`,
and looping forever over an infinite sequence of streams. It never terminates and
never raises.

So `__getitem__` cannot be added alone; it drags in `__iter__` defined-to-raise.
That is affordable, but it buys `s[10:20]` as an alias for `.skip(10).limit(10)`,
which is what Java says and is clearer. Excluded, and the reason recorded — this
is exactly the kind of finding that gets rediscovered otherwise.

Note the ordering dependency this creates: were `__getitem__` ever added, the
`__iter__` refusal must land in the same change, never after.

### The refusals are specified, not merely absent

A requirement stating that `__len__`, `__iter__`, `__contains__`, `__getitem__`,
`__reversed__` and `__eq__` are not implemented looks like specifying nothing.
It is not: each has a `TypeError` that callers will encounter, and the difference
between "we decided" and "nobody thought about it" is invisible in code and
visible in a spec. This is the same failure the roadmap recorded when README's
parity tables could not express absence — a method with no row was invisible
rather than deferred.

`__eq__` is the one with a live default rather than a `TypeError`: identity
comparison, which is correct and is pinned so it cannot drift into consuming
comparison later.

### Why `with` and not `async with`

`CloseHandler` is a plain no-arg sync callable and `close()` invokes handlers
without awaiting. The synchronous protocol is therefore the honest match for the
contract as it stands. Adding `__aenter__`/`__aexit__` would be a claim about
the close-handler contract — that a handler may be awaitable — which is a change
to `stream-close-handling`, not to this capability. Parked in the roadmap's
**Later** so the question survives the decision.

## Risks / Trade-offs

- **`__bool__` raising will surprise someone.** → That is the intent; the
  surprise replaces a silent wrong answer. Mitigated by the message naming what
  to call instead.
- **`__aiter__` makes it easier to iterate a stream by accident where a terminal
  was meant.** → `iterator()` already permitted it and carries the same contract;
  the operator changes ergonomics, not semantics.
- **`__add__` sets a precedent for further operator sugar (`|` for collect, `*`
  for flat_map).** → Real. The spec's framing — one expansion, argued as an
  exception, delegating entirely — is the guard. Each future operator has to make
  its own case rather than inheriting this one's.
- **`__repr__` on a stream carrying a chain seeded by `concat()` will show a
  stage the caller did not write.** → Truthful, and noted in
  `concat-carries-characteristics` as worth a look when this lands.

## Migration Plan

Additive except `__bool__`. Nothing that worked before stops working; code
relying on a `Stream` being truthy was relying on a wrong answer and now raises
at the point of the mistake.

Sequencing: **must land after `concat-carries-characteristics`**, or `__add__`
ships an operator that silently drops its operands' executor and ordering.

## Open Questions

- Whether the parity tables in README grow a section for Python protocols, or
  whether these live only in the capability spec. The tables are declared total
  over Java 8's surface and dunders are not Java methods, so they need a stated
  place rather than becoming invisible rows — but the shape of that place does
  not affect this change's specs, approach or tasks.
