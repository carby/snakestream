## Why

`Stream.concat(a, b)` returns `Stream(_concat(a.iterator(), b.iterator()), a._close_handlers + b._close_handlers)` — always a base `Stream`, always `SEQUENTIAL`, with an **empty chain**. Each operand's own executor is honoured for its own ops, because `iterator()` goes through `self._executor.elements(...)`, so the *elements* are right. Everything downstream of the concat is not.

Java's `Stream.concat` documents one sentence this implementation violates twice: *"The resulting stream is ordered if both of the input streams are ordered, and parallel if either of the input streams is parallel."*

- **The executor is dropped.** `Stream.concat(a.parallel(), b.parallel()).is_parallel()` is `False`. Ops added after the concat then run sequentially where Java would race them.
- **The ordering characteristic is dropped.** `Stream.concat(a.unordered(), b.unordered())._is_ordered()` is `True`, because the empty chain folds to ordered unconditionally. `unordered()` is documented as *the* performance lever under racing, and concat silently revokes it: `concat(a.unordered(), b.unordered()).parallel().limit(5)` pays a barrier Java would not.
- **The operands are not consumed, and the result then silently lies.** `iterator()` runs `_check_not_consumed()` but never sets it — deliberately, since `stream-iterator` requires it to compose non-destructively. So after `c = Stream.concat(a, b)`, `a` is still live, and `await a.collect(to_list())` drains the shared source out from under `c`, which then yields only `b`'s elements. Measured: `[1, 2, 3]` then `[4, 5]`, no exception. Java raises here — `AbstractPipeline` marks its operands `linkedOrConsumed` and a later operation throws `IllegalStateException`.

This is wrong today with zero subclasses in play, which is why it is a change of its own rather than fallout from `derive-without-reinit`.

## What Changes

- **The concatenated stream's executor is `RACING` if either operand is parallel**, `SEQUENTIAL` otherwise — Java's `a ∥ b`.
- **The concatenated stream is unordered if either operand is unordered**, ordered otherwise — Java's `a ∧ b`. Implemented by seeding the result's chain with an `_UnorderedOp()` rather than by adding state: `pipeline-immutability` requires that "the pipeline's ordering characteristic SHALL NOT be carried as separate state alongside the chain", so a field is not available, and a stage is the correct mechanism — `unordered()` is a pipeline stage in Java for this same reason, and this is a stage the concat itself introduces.
- **BREAKING: `concat()` consumes both operands.** Using `a` or `b` for any further intermediate or terminal operation after `Stream.concat(a, b)` raises `IllegalStateException`, matching Java and replacing today's silent wrong answer. `concat()` marks them itself rather than changing `iterator()`, whose non-destructive composition is a requirement of `stream-iterator` that other callers depend on.
- **The result is a base `Stream`, and this is now stated rather than incidental.** With `type(a)` and `type(b)` potentially different subclasses there is no principled choice, and Java returns an internal type for exactly that reason. Documented as a decision, not fixed.
- Close-handler behaviour is unchanged: `a`'s handlers then `b`'s, snapshotted at call time, already specified and already correct.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-concat`: adds requirements for the result's execution mode, its ordering characteristic, its concrete type, and the invalidation of both operands. Its existing element-order, laziness and close-handler requirements are unaffected.
- `pipeline-immutability`: `concat()` becomes an *extending* operation for its operands. Its existing scenario "A merely-consumed (never extended) stream passed to concat() does not raise" still holds for the operand's state *on the way in*; what changes is the operand's state *on the way out*.

## Impact

- `src/snakestream/stream.py` — `Stream.concat()` only.
- `openspec/specs/stream-ordering` describes ordering as a fold over the chain and is the reason the `_UnorderedOp` seeding is the available mechanism; no requirement there changes.
- Blocks `implement-python-data-model`'s `__add__`, which is sugar over `concat()` and would otherwise inherit all three defects.
