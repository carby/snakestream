## Why

The Sink-chain redesign converted the intermediate operations to the push protocol but explicitly scoped out the terminals (design decision (a): "push stays internal only"). The result is a half-converted pipeline with two live consequences:

- **Every element makes a pointless round trip.** A terminal calls `_compose()`, which drives the push chain into `GeneratorBridgeSink`, which buffers the element into a list so `_drive()`'s loop can yield it so the terminal can push it into its own accumulator — push → buffer → pull → push, per element, on every terminal call in the library.
- **Short-circuiting terminals cannot participate in cancellation.** `any_match`, `all_match`, `none_match`, `find_first` and `find_any` stop by abandoning the generator. They cannot tell an upstream `_LimitSink` or a `_FlatMapSink`'s inner loop to stop, so a `.flat_map(...)` feeding an `any_match` keeps expanding the current inner stream after the answer is already known — the same class of bug `limit()` was fixed for when cancellation was introduced.

The `TerminalSink` seat that the redesign shipped is also currently scaffolding: its `_create_container()` / `_finish()` / `result()` apparatus has exactly one subclass, `GeneratorBridgeSink`, which overrides most of it. Writing the first real terminal sinks is what makes that seat load-bearing — and it is the shape the **Next**-bucket `Collector(supplier, accumulator, combiner, finisher)` redesign plugs into.

## What Changes

- Add `BaseStream._drive_to(terminal)`: links the chain onto a real `TerminalSink`, pushes source → head → terminal, and returns `terminal.result()`. Sibling to `_drive()`, which keeps returning a generator via the bridge.
- Add `BaseStream._drive_to_sequential(terminal)` for the ordered terminals, mirroring today's `_drive(self._chain[:], self._stream)` escape hatch. `_drive_to()` is the dispatching form; `ParallelStream` overrides it.
- Convert the terminal operations to `TerminalSink` subclasses in a new `terminals.py`: `reduce` (both overloads), `count`, `for_each` / `for_each_ordered`, `_match` (backing `all_match` / `any_match` / `none_match`), `_min_max` (backing `max` / `min`), `find_first` / `find_any`, and `collect`'s 3-arg mutable-reduction form.
- Short-circuiting terminal sinks report `cancellation_requested()` once their answer is fixed, so upstream `limit()` and `flat_map()` stop immediately — new behavior, additive (fewer upstream calls; the returned value is unchanged).
- `ParallelStream` overrides `_drive_to()` to push the racing `_compose()` generator's elements into the single terminal sink, preserving today's parallel semantics exactly. It gains cancellation only at the outer loop (it stops pulling from the race); per-branch cancellation is out of scope.
- Keep `_drive()` / `GeneratorBridgeSink` for what genuinely needs a generator: `iterator()`, the `sequential()` / `parallel()` handoff, `_concat`, and every collector (so `collect(collector)` and `to_array()` are unchanged).
- No public API change. Every terminal keeps its current signature, return type, and result for every input.

## Capabilities

### New Capabilities
- `terminal-sinks`: terminal operations execute as `TerminalSink`s driven by a push loop, including short-circuiting terminals requesting cancellation upstream, and the ordered-drive variant used by `for_each_ordered()` / `ParallelStream.find_first()`.

### Modified Capabilities
- `sink-protocol`: the "Terminal sink produces a result" requirement gains the contract for a short-circuiting terminal sink (reporting `cancellation_requested()` from the point its result is fixed, and still receiving `end()`), and the driving loop's obligation to return `result()` rather than yield.
- `pipeline-composition`: `limit()`'s no-over-pull requirement and `flat_map()`'s inner-generator requirement extend to cancellation originating at a *terminal* sink, not only at a mid-chain `limit()`.

## Impact

- **Code**: new `src/snakestream/terminals.py`; `base_stream.py` (`_drive_to`, `_drive_to_sequential`); `stream.py` (terminal method bodies become sink construction + one `_drive_to` call); `parallel_stream.py` (`_drive_to` override, `find_first` override rewritten in terms of it). `sink.py` unchanged unless the `TerminalSink` base needs a documented cancellation hook. `collector.py`, `ops.py`, `sort.py`, `callable_dispatch.py` untouched.
- **Performance**: expected to recover part of the buffer-and-yield overhead the bridge gives back — the redesign measured ~24.5% overall and noted the bridge as the leak. Sequential terminals only; parallel keeps the bridge. To be measured on the same harness (Python 3.14.5, 20,000 elements, best of 5) and recorded, not assumed.
- **Tests**: existing terminal-op suites should pass unmodified — that is the primary regression signal. New coverage for cancellation reaching upstream from a terminal, and for the ordered-drive path.
- **Docs**: README needs no edit (no public API surface changes). Roadmap's **Now** entry moves to **Done**; the **Next**-bucket Collector redesign is unblocked.
