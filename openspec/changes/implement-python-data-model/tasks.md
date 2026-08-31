> **Sequencing:** this change must land **after** `concat-carries-characteristics`. `__add__` delegates to `Stream.concat()`, so landing first would ship an operator that drops its operands' executor and ordering.

## 1. Asynchronous iteration

- [ ] 1.1 Implement `__aiter__` as a delegation to `iterator()`, adding no behaviour of its own.
- [ ] 1.2 Test that `async for x in stream` yields what `async for x in stream.iterator()` yields, over a pipeline with a queued chain.
- [ ] 1.3 Test that invoking `__aiter__` pulls nothing until the iterator is driven, using a `peek` side effect.
- [ ] 1.4 Test that an ordered parallel stream iterates in encounter order, and that an already-extended reference raises `IllegalStateException`.

## 2. Context-manager protocol

- [ ] 2.1 Implement `__enter__` returning `self`, and `__exit__` calling `close()` and returning a falsy value so exceptions propagate.
- [ ] 2.2 Test handler invocation on normal exit, on an exception propagating out of the body, and in registration order for two handlers.
- [ ] 2.3 Test that entering an already-extended reference does not raise, `on_close()`/`close()` being exempt from invalidation per `pipeline-immutability`.
- [ ] 2.4 Confirm the existing `contextlib.closing()` tests still pass — the wrapper stays supported, it just stops being required.

## 3. `__repr__`

- [ ] 3.1 Implement `__repr__` reporting concrete type, queued chain and execution mode. Decide the rendering of an op — the op classes are private, so pick a stable short form and keep it in one place.
- [ ] 3.2 Test that it names type, chain and mode; that it pulls nothing; and that it does not raise on an extended or consumed stream.
- [ ] 3.3 Check the rendering against a chain seeded by `concat()` — the ordering stage that change introduces will appear here, and it should read as truthful rather than as a bug.

## 4. `__bool__`

- [ ] 4.1 Implement `__bool__` raising `TypeError`, with a message naming the asynchronous alternative a caller asking "is this empty" should reach for.
- [ ] 4.2 Test `bool(stream)`, `if stream:` and `not stream` all raise, and that an empty stream raises rather than evaluating true.
- [ ] 4.3 Test the message names an async alternative, so the guidance cannot be dropped silently.

## 5. `__add__`

- [ ] 5.1 Implement `__add__` delegating to `Stream.concat(self, other)` for a `Stream` operand and returning `NotImplemented` otherwise.
- [ ] 5.2 Test that `a + b` yields `a`'s elements then `b`'s, and that its mode, ordering, type and handlers match `Stream.concat(a, b)`.
- [ ] 5.3 Test that `a + b` invalidates both operands, and that `a + [1, 2]` and `a + "xs"` raise `TypeError` without coercion.
- [ ] 5.4 Test that `a + b + c` chains — the reason no n-ary `concat` is needed.

## 6. Pin the refusals

- [ ] 6.1 Test that `list(stream)`, `len(stream)`, `x in stream`, `stream[0]` and `stream[1:3]` each raise `TypeError`, and that none of them consumes the stream.
- [ ] 6.2 Test that `==` on two distinct streams over equal sources is `False` and consumes neither.
- [ ] 6.3 Add a comment beside the implemented dunders recording that `__getitem__` is excluded because Python synthesizes iteration from it when `__iter__` is absent — the finding most likely to be rediscovered.

## 7. Documentation

- [ ] 7.1 Update CLAUDE.md's AutoClose section: `with stream:` is now the idiom and `contextlib.closing()` the fallback.
- [ ] 7.2 Give README a stated place for Python protocols. The parity tables are declared total over Java 8's surface and dunders are not Java methods, so they must not become invisible rows — see design.md's open question.
- [ ] 7.3 Show `async for` and `a + b` in README where `iterator()` and `Stream.concat()` are currently demonstrated.

## 8. Validation

- [ ] 8.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [ ] 8.2 `uv run pytest --cov-fail-under=98`.
- [ ] 8.3 `openspec validate implement-python-data-model`.
