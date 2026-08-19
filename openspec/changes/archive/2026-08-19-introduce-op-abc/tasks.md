## 1. Add the `Op` ABC

- [x] 1.1 In `src/snakestream/sink.py`, add an `Op(ABC)` class with a docstring stating the op/sink pairing: abstract `link(self, downstream: Sink[Any]) -> Sink[Any]`, and concrete `make_shared_state(self) -> Any` returning `None`, documented as "no shared state" with the note that a stateful op returns a container, never `None`.
- [x] 1.2 Run `uv run ty check src` — should be clean, nothing consumes `Op` yet.

## 2. Make the shipped ops implement it

- [x] 2.1 In `src/snakestream/stream.py`, import `Op` from `snakestream.sink` and make the five stateless ops subclass it: `_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`. No other edits to these classes.
- [x] 2.2 Make the three stateful ops subclass it: `_DistinctOp`, `_LimitOp`, `_SkipOp`. Keep each `make_shared_state()` override exactly as written.
- [x] 2.3 Run `uv run pytest` — full suite green with no test changes.

## 3. Type the chain against `Op`

- [x] 3.1 In `src/snakestream/base_stream.py`, import `Op` and change `self._chain: list[Any]` to `list[Op]` and `_derive(self, op: Any)` to `_derive(self, op: Op)`.
- [x] 3.2 Change `_sequential(self, intermediaries: list[Any], terminal: Sink[Any])` to take `list[Op]`, and `_drive(self, chain: list[Any], ...)` to take `list[Op]`.
- [x] 3.3 In `src/snakestream/parallel_stream.py`, change `_parallel(self, intermediaries: list[Any], ...)` to take `list[Op]`.
- [x] 3.4 Run `uv run ty check src`. Fix anything it flags at the chain's call sites (`op.link(...)`, `op.make_shared_state()`). If it flags something outside those, fix it only if it is a one-liner; otherwise record it in the change and leave the ops' internals alone (the next roadmap item rewrites them).

## 4. Replace the `getattr` sniff

- [x] 4.1 In `ParallelStream._parallel`, replace the `getattr(op, "make_shared_state", None)` block with an unconditional `state = op.make_shared_state()` and an `if state is not None: state_map[op] = state`.
- [x] 4.2 Run `uv run pytest` — in particular the parallel `distinct`/`limit`/`skip` tests, which are what the state map exists for.

## 5. Tests

- [x] 5.1 Add a test module (e.g. `tests/test_op_protocol.py`) asserting every shipped op class is a subclass of `Op`, so a future op cannot silently skip the base class.
- [x] 5.2 Add a test that a minimal `Op` subclass defining only `link()` returns `None` from `make_shared_state()`, and that instantiating an `Op` subclass without `link()` raises `TypeError`.
- [x] 5.3 Add a test that `make_shared_state()` on a stateful op returns a fresh, empty, non-identical container on each call.
- [x] 5.4 Add a test that building the parallel state map over a chain of mixed stateful and stateless ops produces entries only for the stateful ones, keyed by the op object.
- [x] 5.5 Add a test that a sink built from a stateless op handles `begin({})` and propagates `begin()` downstream.

## 6. Validate

- [x] 6.1 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 6.2 `uv run ty check src`
- [x] 6.3 `uv run pytest --cov-fail-under=98`
- [x] 6.4 Confirm no public API surface changed, so README's parity tables need no edit.
- [x] 6.5 Move the `Op` ABC item from **Now** to **Done** in `roadmap.md`, noting that it unblocks the op-class-collapse item.
