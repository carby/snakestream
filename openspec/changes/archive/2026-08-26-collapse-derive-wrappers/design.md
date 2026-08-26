## Context

See proposal.md - Why. What matters for the approach is the shape as it stands
and the two prior swings at it, since this design is only defensible against
that history:

```
pre 08-24   _derive(op) + _derive_executor(exec)     two 5-field copiers, duplicated
08-24       merged -> _derive(chain, executor)       _derive_executor DELETED; its
                                                     12-line docstring copied verbatim
                                                     onto BOTH public methods
08-25       _extend(op) added over _derive           kills 8 cast+chain lines at the
                                                     op call sites. _derive_executor
                                                     deliberately NOT folded in
08-26       _derive_executor RE-ADDED                because CLAUDE.md already claimed
                                                     it existed, and the docstring was
                                                     duplicated across two methods
```

The 2026-08-24 merge did not fail because one copier is wrong. It failed on two
specific costs, and the 2026-08-25 batch then paid one of them back with
`_extend` while explicitly declining to touch the other. Both costs are
addressable without keeping either wrapper, which is the whole of this design.

Constraint from `pipeline-immutability`: a derivation must return a new
instance and invalidate the receiver, with `_check_not_consumed()` before the
copy and `self._consumed = True` after it, so that a raising copy leaves the
receiver valid. Constraint from `stream-execution-model`: a mode switch must
carry the queued chain over **uncomposed**, which is what makes `.parallel()`
position-independent.

## Goals / Non-Goals

**Goals:**

- One derivation method, with the chain-extension rule still in exactly one
  place.
- Call sites no longer noisier than today's: nine op methods stay one-liners.
- The pipeline-immutability warning ends up wherever the temptation to violate
  it actually lives after the change, rather than wherever it happened to live
  before.
- Every stale prose reference to the deleted names is corrected in the same
  change, not left for a later reader to resurrect from.

**Non-Goals:**

- Reducing the layer count below one. `_check_not_consumed()`, `_compose()` and
  `_evaluate()` are out of scope; `_compose()`'s fate is tracked separately in
  `collapse-compose-into-iterator`.
- Any change to when a stream is consumed, what a derived stream carries, or
  what any public method returns.
- Making execution mode an `Op`. That would collapse the mode switch into the
  chain entirely, and it is already rejected on design grounds: `unordered()`
  is an op *because* it is positional, and `parallel()` must not be, per Java,
  where `parallel()` sets a flag on the source stage.

## Decisions

### 1. `_derive()` takes the `Op`, not a pre-built chain

`def _derive(self, op: Op | None = None) -> Stream[Any]`, appending internally:

```python
new_stream._chain = [*self._chain, op] if op is not None else self._chain
```

*Why over `_derive(chain, executor)` with both defaulted.* Taking a chain is
what forced the 2026-08-25 regression: with the chain built by the caller, the
nine op methods each spell out `[*self._chain, op], self._executor`, and the
`Op` each method is *about* becomes the least visible part of the line. Taking
the `Op` puts the rule in the callee and leaves `self._derive(_MapOp(mapper))`
at the call site — identical to `_extend`'s ergonomics, which is the property
that has to survive.

*Why `op` and not `op_cls, *args`.* Settled already, and unchanged here: the
nine `Op` constructors take between zero and two arguments of unrelated types,
so a class-plus-args form degrades to `*args: Any` and discards exactly the
type information the call site has.

*Why `is not None` and not `if op`.* All `Op` instances are truthy today, but
`_UnorderedOp` carries no state and links to no sink; an `Op` that later grew
`__len__` or `__bool__` would be silently dropped from the chain by a
truthiness test. The explicit test costs nothing and cannot fail that way.

### 2. The executor is set by `sequential()` / `parallel()`, not passed to `_derive()`

```python
def sequential(self) -> Stream[T]:
    derived = self._derive()
    derived._executor = SEQUENTIAL
    return derived
```

*Why over a second `executor: Executor | None = None` parameter on `_derive()`.*
The alternative works and is one line shorter per mode method:

| | `_derive(op=None, executor=None)` | chosen: `_derive(op=None)` + assign |
|---|---|---|
| axes in the copier | 2 | 1 |
| sentinels | 2 | 1 |
| relies on `Executor` truthiness for `executor or self._executor` | yes | no |
| mode-method body | 1 line | 3 lines, x2 |
| where `_executor` is set | one place | two: copier sets, caller overwrites |

The deciding factor is not the line count but what each form makes visible. The
parameter form hides the mode switch inside a method that nine chain-extension
call sites also use; the assignment form puts "same chain, different executor"
in the two bodies it describes, where a reader looking for what `.parallel()`
does finds it. It also removes any reliance on `Executor` instances being
truthy — true today (`Sequential`/`Racing` are plain ABC subclasses with no
`__bool__`/`__len__`) and relied on by `_evaluate()`, but not something a second
site needs to depend on.

*Accepted cost:* `_executor` is no longer assigned exactly once per instance. It
is set by the copier and then overwritten by the caller. The window between the
two statements is not observable — no `await` separates them and the derived
stream has not escaped — but if `_derive()` ever gains an `await` or a hook, this
becomes a real hazard, and that is the trade being made knowingly.

### 3. `_derive()` stays a method on `Stream`

Considered: moving derivation to module level, in the style of `execution.py`'s
`_wrap_sink` / `_copy_into` / `stream_through`. Rejected. That module states its
own membership rule in the comment above the family — "Each function has exactly
one meaning, and **none of them needs a stream instance**" — and derivation
cannot satisfy it:

```
                 takes          returns          needs a Stream?
--------------------------------------------------------------------
_wrap_sink       chain, sink    Sink             no
_copy_into       sink, src      value            no
stream_through   chain, src     AsyncGenerator   no
feed_through     chain, src, t  value            no
--------------------------------------------------------------------
_derive          a Stream       a Stream         it IS the thing
```

Those four are algorithms over a stream's *parts*. `_derive()` is a constructor
plus a receiver-invalidation: it reads four private attributes, writes two on a
new instance and one on the receiver, and the `self._consumed = True` it
performs *is* the `pipeline-immutability` invariant. An invariant enforced from
outside the class is one every future call site can route around.

*This is not blocked on `spliterator()` or on partitioned execution.* Checked
against the roadmap rather than assumed: real parallelism is recorded as landing
as **a third `Executor` implementing `elements()`/`value()`**, and both take
`(chain, source)`. Partitioned execution would split the *source* and run
*chains*; `spliterator()` itself would consume a composed stream into a pull
bridge. Neither constructs a `Stream`, so neither creates the payoff a
module-level `_derive()` would need. The only future that would is
partition-plus-combine wanting per-partition `Stream` objects, and that is
already set aside under the stated rule "Java is the public-API contract, not
the implementation blueprint." The boundary this preserves is `Stream` owning
identity and lifetime, `execution.py` owning algorithms over the parts, with
`_compose()`/`_evaluate()` as the two-line border guards.

### 4. The immutability warning moves onto `sequential()`

`_derive_executor()`'s docstring carries two warnings, and the change affects
them in opposite directions:

- *"It must not compose"* becomes largely structural. The new body derives and
  assigns a field; there is nowhere a `_compose()` call could plausibly sit. It
  is kept, shortened.
- *"It must not assign onto self and return self"* becomes **more** important,
  not less, because the new body is a working template for the forbidden move:

  ```python
  derived = self._derive()
  derived._executor = RACING  # delete two chars and a line, and this is
  return derived  # self._executor = RACING; return self
  ```

  It is kept at full length and moves onto `sequential()`, where the temptation
  now is, with `parallel()` pointing at it — the same indirection `parallel()`
  already uses today ("see `_derive_executor()`").

Rejected: leaving it on `_derive()`, which after this change has nothing to do
with execution mode; and duplicating it onto both public methods, which is
exactly what the 2026-08-24 merge did and what caused the method to be
resurrected.

### 5. Stale prose is corrected in the same change

`CLAUDE.md:61` names `_derive_executor()`; `CLAUDE.md:34` names `_derive()` (and
stays correct); `roadmap.md`'s 2026-08-24 entry records the immutability
rationale *by method name* at line 1195, and the 2026-08-25 entry describes
`_extend` at lines 727-745. History entries are not rewritten to pretend the
prior shapes never existed — they are annotated to say what superseded them.
This is not tidiness: `_derive_executor()` was re-added in the first place
*because* `CLAUDE.md` described a method that did not exist, and the same
mechanism would run again.

## Risks / Trade-offs

- [The change reads as a revert of the 2026-08-24 merge, and gets reverted back
  by a future reader] → The proposal and this design both state what was
  different about that merge's failure modes and how each is paid for here; the
  roadmap **Done** entry must say the same when the change is archived.
- [`_executor` set twice per mode switch (Decision 2)] → Not observable: no
  `await` between the statements, the instance has not escaped. Recorded here so
  that adding an `await` to `_derive()` is recognised as breaking it.
- [The new `parallel()` body demonstrates the in-place mutation
  `pipeline-immutability` forbids] → The warning moves to where that temptation
  now lives (Decision 4), and `pipeline-immutability`'s existing scenarios cover
  the behaviour: a mode switch invalidates the receiver, and the derived stream
  is unaffected.
- [`op is not None` reads as defensive over a condition that cannot occur today]
  → One line, and Decision 1 records the specific future that makes it matter.
- [Silent behaviour change hidden by a green suite] → The tripwire is that no
  test file is edited at all: `git diff -- tests/` must be empty. The existing
  `pipeline-immutability`, `pipeline-composition` and `stream-execution-model`
  tests already pin every contract this touches, including that a queued chain
  survives a mode switch and that `.parallel()` is position-independent.

## Migration Plan

None. No public surface changes, so there is nothing to migrate and no entry for
README's migration log. Rollback is `git revert` of a single commit touching one
source file.
