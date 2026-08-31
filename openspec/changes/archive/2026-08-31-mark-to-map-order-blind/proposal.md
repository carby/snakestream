## Why

The roadmap's **Open questions needing a session** carries one item:
*does `to_map()` declare `Characteristics.UNORDERED`?* It is the last survivor of
the seven questions that section opened, and `mark-order-blind-collectors`
(2026-08-31) settled the rest of the collector family on a tail-latency
benchmark while deliberately leaving this one out, naming two obstacles the
benchmark does not address: the no-merge form **raises** on a duplicate key and
reordering can change *which* key the message names, and a caller-supplied
`merge_function` need not commute.

Both obstacles are real, and they point in opposite directions — which is why
the answer is not one answer. `to_map()` is two collectors behind one factory,
and they differ in exactly the property `UNORDERED` asserts.

## What Changes

- **`to_map(key_mapper, value_mapper)` — the no-merge form — declares
  `Characteristics.UNORDERED`.** With no merge function the collected `dict` is
  exactly order-invariant: keys and values are each a function of the element
  alone, `dict.__eq__` is insensitive to key order, and every key is distinct or
  the collection raises. So any two orderings of the same elements collect to a
  result that compares equal, which is the whole of what `UNORDERED` claims.
- **`to_map(key_mapper, value_mapper, merge_function)` — the 3-arg form —
  declares nothing, permanently.** `merge_function` is caller-supplied and need
  not commute: `lambda a, b: a` keeps whichever value arrived first, and string
  concatenation orders its operands. The collected value therefore genuinely
  differs under reordering, so the declaration would be false. This is stated as
  a requirement, not left silent, on the precedent
  `mark-order-blind-collectors` set for `summing_double()` and the
  `averaging_*` family: an order-sensitive-*in-fact* collector gets a written
  exclusion so the question is closed rather than merely unasked.
- The declaration is therefore **decided per call**, from whether
  `merge_function is None` — the first collector in the library whose
  characteristics depend on its arguments rather than on its identity or on a
  downstream's declaration.
- The duplicate-key message becomes **nondeterministic under `RACING`** when a
  stream contains two or more *distinct* collisions: skipping the barrier means
  the branches may reach the second collision first, so
  `IllegalStateException` may name either colliding key. Whether the collection
  raises at all is unchanged — a duplicate key exists independently of the order
  the elements arrive in. The spec says so explicitly rather than leaving a
  reader to infer it from the mark.
- `to_map()`'s order-blind path is verified **by observation**, not by the
  declaration/mechanism pair the integer collectors use: a `dict` *does* betray
  arrival order through its key iteration order, even though `==` ignores it, so
  the stronger guard `racing-encounter-order` already prefers is available here.

No benchmark is re-run. The barrier's cost is a property of `race_through()`
rather than of the collector behind it, and `mark-order-blind-collectors`
measured it at 1.12–1.27x on tail-latency IO work. The question this change
answers is semantic, not empirical, which is exactly why that benchmark could
not settle it.

Not breaking. A collector's declared characteristics are public surface, but the
value a correct `to_map()` collection produces is unchanged, and under
`SEQUENTIAL` the mark has no effect at all. The one observable change is the key
named by a duplicate-key exception under `.parallel()`, on a failure path where
the library already promises only that *a* colliding key is named.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-to-map`: gains a requirement that the 2-arg form declares
  `UNORDERED` and the 3-arg form SHALL NOT, and a requirement stating what the
  mark does and does not promise about the duplicate-key exception under
  `RACING`.
- `racing-encounter-order`: its order-blind-path verification requirement gains
  `to_map()` as a case verified by observation, since a `dict`'s key iteration
  order is exactly the arrival-order evidence the integer collectors lack.

## Impact

- `src/snakestream/collectors.py` — `to_map()`'s `Collector(...)` call gains a
  `characteristics` argument computed from `merge_function`, plus the comment
  recording why the two forms differ.
- `tests/test_to_map.py` — declaration assertions for both forms.
- `tests/test_racing_delivery_order.py` — the observation test for the no-merge
  form, and a test pinning that the 3-arg form still gets its barrier.
- `roadmap.md` — the **Open questions needing a session** section empties and is
  removed; the question moves to **Done**.
- No change to `collect()`'s dispatch, to `Collector`, or to any executor. This
  change adds declarations, not mechanism.
