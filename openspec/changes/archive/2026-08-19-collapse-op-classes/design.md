## Context

See `proposal.md` — Why. The relevant current state:

- `sink.py` holds the protocol: `Sink`, `Op`, `IntermediateSink`, `TerminalSink`,
  `GeneratorBridgeSink`. Names there are unprefixed but nothing in it is
  exported from `snakestream/__init__.py`, which exports only `Stream`.
- `stream.py` lines 46-276 hold the eight op/sink pairs; lines 278+ hold the
  public `Stream` API. Splitting those into `ops.py` is the *next* roadmap item,
  deliberately sequenced after this one.
- Three sinks are stateful in the sense that matters to this codebase: their
  state is shared across `ParallelStream`'s racing branches, delivered through
  `begin(state_map)` and keyed by the originating `Op` object.
  `parallel_stream.py:36-39` builds that map by calling `make_shared_state()`
  on every op and keying only non-`None` results.
- `_LimitSink.accept` reserves its slot *before* awaiting downstream, and that
  ordering is load-bearing across racing branches (`stream.py:225-231`).

## Goals / Non-Goals

**Goals:**

- One place where "an op holds its arguments and builds its sink" is written.
- One place where "a sink resolves its shared state at `begin()`" is written,
  and one place where an op's state shape is stated.
- `_LimitSink.accept`'s race comment readable in the notation it describes.

**Non-Goals:**

- Moving op/sink definitions out of `stream.py` — that is the next roadmap item,
  and doing it here would turn a move into a move-plus-rewrite.
- Touching the per-element dispatch shape in `_FilterSink`/`_MapSink`/
  `_PeekSink`. That duplication was measured and deliberately accepted
  (`archive/2026-08-18-add-callsite-dispatch`); it is not in scope and must not
  be "tidied" in passing.
- Converting terminals to `TerminalSink`s, or any change to `TerminalSink`,
  `GeneratorBridgeSink`, or the driving loop.
- Any public API or observable behavior change.

## Decisions

### Two op bases, split on shared state, in `sink.py`

`StatelessOp` and `StatefulOp`, both storing `*args` and forwarding to a
class-level `_sink_cls`; `StatefulOp.link()` additionally passes `self` so its
sink can key the state map.

```python
class StatelessOp(Op):
    _sink_cls: ClassVar[Callable[..., Sink[Any]]]

    def __init__(self, *args: Any) -> None:
        self._args = args

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, *self._args)


class StatefulOp(Op):
    _sink_cls: ClassVar[Callable[..., Sink[Any]]]

    def __init__(self, *args: Any) -> None:
        self._args = args

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, self, *self._args)
```

Five ops become `class _MapOp(StatelessOp): _sink_cls = _MapSink`; three become
the same against `StatefulOp` plus a one-line `make_shared_state()`.

*Why two bases and not one:* passing the op to every sink would give five
stateless sinks a constructor parameter they never read. The split is also the
axis the code already turns on — `parallel_stream.py` divides ops into exactly
these two groups by `make_shared_state()`'s result.

*Why in `sink.py` and not `stream.py`:* they are protocol-level, they sit
directly under the `Op` ABC that specifies them, and leaving them in `stream.py`
would mean moving them again in the next roadmap item.

*Alternative rejected — a single generic `Op` factory* (`Op(sink_cls, *args)`
instantiated inline rather than subclassed): it would erase the op *types*,
which are what the state map is keyed by and what a reader greps for. Subclasses
keep `_LimitOp` a name in tracebacks and in `ty`'s output.

### "Stateful" here means *shared* state, and `_SortedOp` is `StatelessOp`

`_SortedSink` buffers the whole stream — it is stateful in Java's sense — but
its buffer is per-sink and never shared, so it has no `make_shared_state()` and
belongs on `StatelessOp`. The naming follows Java's `StatelessOp`/`StatefulOp`
pair, and the class docstrings will state the axis explicitly so the
`_SortedOp` case does not read as a mistake. The alternative names
(`SharedStateOp` / plain `ArgsOp`) are more literally accurate but drop the
Java-parity naming this project prefers, for a distinction one docstring
settles.

### `StatefulSink` resolves state from the op's own factory

```python
class StatefulSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], op: Op) -> None:
        super().__init__(downstream)
        self._op = op
        self._state: Any = None

    async def begin(self, state_map: StateMap) -> None:
        shared = state_map.get(self._op)
        self._state = self._op.make_shared_state() if shared is None else shared
        await super().begin(state_map)
```

This collapses the three hand-written `begin()` overrides and, more
importantly, deletes the duplicated default: today `_LimitOp.make_shared_state()`
returns `[0]` and `_LimitSink.__init__`/`begin()` separately write `[0]`, so the
op's declared state shape and the sink's fallback shape are two independent
statements. Sourcing the fallback from `make_shared_state()` makes it one — the
requirement this change adds to the `sink-protocol` spec.

`self._state` is `None` until `begin()`. The spec already requires `begin()`
before the first `accept()`, and every sink here is built by `_sequential()`
and begun by `_drive()`, so no `accept()` can observe the `None`.

The three sinks then read `self._state` rather than `self._seen` /
`self._count` / `self._skipped`. The descriptive names are lost; the bodies are
two to six lines each and the loss is judged acceptable against three fewer
`begin()` overrides. Per-sink read-only properties aliasing `self._state` were
considered and rejected as more machinery than the names are worth.

### A `Counter` type replacing the one-element lists

```python
class Counter:
    """A mutable integer box: an op's shared count, passed through the state
    map so racing branches increment one instance."""

    __slots__ = ("value",)

    def __init__(self, value: int = 0) -> None:
        self.value = value
```

`_LimitOp`/`_SkipOp`'s `make_shared_state()` return `Counter()`; the sinks read
`self._state.value`. This is what makes `_LimitSink.accept` legible:

```python
if self._state.value >= self._max_size:
    self._cancelled = True
    return
# reserve the slot before pushing downstream: ...
self._state.value += 1
```

*Alternatives:* `itertools.count` (no readable current value, cannot be
compared), `list[int]` (the status quo), a `dataclass` (generates `__eq__` and
`__repr__` this does not need, and does not combine with `__slots__` before
3.10's `slots=` — supported, but for no gain). The name shadows nothing this
repo imports; `collections.Counter` is a multiset and is not used anywhere in
`src/`. Lives in `sink.py` next to `StatefulSink`, its only consumer, rather
than `type.py`, which holds type *aliases* rather than runtime classes.

### Test doubles keep subclassing `Op`

`tests/test_sink.py` and `tests/test_sequential.py` build fake ops. They stay on
`Op` directly: their job is to pin the protocol, and rewriting them onto the
convenience bases would mean the protocol is only ever exercised through those
bases.

## Risks / Trade-offs

- **`ty` rejects `self._sink_cls(downstream, *self._args)`** if `_sink_cls` is
  typed `type[Sink[Any]]`, since `Sink.__init__` takes no such arguments →
  annotate it `ClassVar[Callable[..., Sink[Any]]]`, which types the call site as
  variadic. A class object stored in a class attribute is not a descriptor, so
  it is *not* bound as a method on access — unlike a plain function or lambda
  would be. Verify with `uv run ty check src`, which CI gates on the 3.14 leg.
- **Per-element cost in `limit`/`skip`** changes from a list index to a
  `__slots__` attribute load; both are single fast opcodes and the swap is not
  expected to be measurable. Everything else changed here runs once per
  composition (`link()`, `begin()`), not per element. Confirm with the standard
  harness rather than assuming.
- **Silent behavior change in the state fallback.** Distinct's fallback is
  `set()` both before and after; limit's and skip's change from `[0]` to
  `Counter()`, which is the same value in a different box. The risk is a missed
  read site still indexing `[0]` → the existing parallel `limit`/`skip` tests
  in `tests/test_parallel.py` cover exactly the shared-state path, and a
  leftover `[0]` on a `Counter` raises `TypeError` rather than passing quietly.
- **Scope creep into the next roadmap item.** The temptation is to move the ops
  to `ops.py` while touching them → explicitly out of scope above; the next
  change moves them unchanged.

## Migration Plan

Not applicable — no public API, no persisted state, no dependency change. The
change is internal and lands in one commit; rollback is a revert.
