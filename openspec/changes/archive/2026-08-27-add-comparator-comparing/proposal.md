## Why

`sorted()`, `min()`, `max()`, `min_by()` and `max_by()` accept only a 3-way
`Comparator`, and a comparator is the most expensive way Python can express an
ordering. Every comparison goes through `cmp_to_key`, which forces a
Python-level `__lt__` call per comparison; an *async* comparator additionally
forces the hand-written `merge_sort` in `sort.py`, because `list.sort` is a C
loop with no point at which control can return to the event loop.

Java has the answer already and snakestream has not ported it:
`Comparator.comparing(keyExtractor)`. Ordering by an extracted key is O(n) key
extractions plus a C-speed Timsort, instead of O(n log n) comparator calls.
Measured 2026-08-26 on this machine, sorting dicts by one field:

| n | sync comparator | sync key | async comparator | async key |
|---|---|---|---|---|
| 1,000 | 1.1 ms | 0.2 ms (**6.8x**) | 2.6 ms / 9,965 awaits | 0.5 ms / 1,000 awaits (**4.8x**) |
| 20,000 | 47.1 ms | 5.3 ms (**8.8x**) | 85.5 ms / 285,754 awaits | 15.7 ms / 20,000 awaits (**5.4x**) |

The sync win is the larger one: this is not an async workaround, it is the
faster way to sort for users who never write `async def`. It also collapses the
async case from O(n log n) interleaved awaits to O(n) awaits gathered up front,
which is what lets that case reach `list.sort` at all.

## What Changes

- **New: `comparing(key_extractor)` in `snakestream.comparator`.** A factory
  returning a `Comparator` that orders by an extracted key. The key extractor
  may be sync or async, like every other user-supplied callable.
- **`comparing()` returns an object, not a closure.** A literal port of Java's
  `(a, b) -> k(a).compareTo(k(b))` would be *worse* than today — the key would
  be called twice per comparison, O(n log n) times, so an async key would cost
  `2n log n` awaits. The returned object therefore exposes the key extractor as
  an attribute so that `sort()` can recognize it and take a
  decorate-sort-undecorate fast path, while still being callable as an ordinary
  `Comparator` for any consumer that does not know about the fast path.
- **`sort()` gains a key fast path.** When handed a `comparing()` comparator it
  extracts keys once, then sorts with `list.sort(key=...)` — no `cmp_to_key`, no
  `merge_sort`, and none of the int/bool contract machinery, which has nothing
  to police when there is no comparator sign involved.
- **No signature changes anywhere.** `comparing()` is passed where a
  `Comparator` already goes, so `sorted()`, `min()`, `max()`, `min_by()` and
  `max_by()` all accept it without modification. This is why the change is a
  factory rather than a `key=` parameter on `sorted()`: one addition upgrades
  every comparator-consuming operation instead of four separate parameters.
- Not breaking. The existing comparator paths, including `merge_sort`, are
  untouched and remain the behaviour for any comparator that is not a
  `comparing()` result.

Explicitly **out of scope**, to keep the change to the one addition that pays:

- `thenComparing()` — genuinely useful, and cheap once the unwrapping mechanism
  exists (a tuple key stays one C sort), but its composition rules should be
  designed after the single-key case has proven the mechanism.
- `reversed()` — already covered by `sorted(reverse=True)`.
- `naturalOrder()` / `reverseOrder()` — `sorted()` with no comparator already is
  natural order.
- Replacing `merge_sort` with a smaller algorithm, and retiring the async
  comparator altogether. Both become easier to judge once `comparing()` exists
  and it is visible how much traffic still reaches the comparator path.

## Capabilities

### New Capabilities
- `comparator-comparing`: the `comparing(key_extractor)` factory — that it
  produces a valid `Comparator` usable by every comparator-consuming operation,
  that the key extractor may be sync or async and is applied exactly once per
  element when sorting, and that ordering by key is stable.

### Modified Capabilities
None. `comparing()` produces a `Comparator` that satisfies the existing
`comparator-contract` unchanged — it is a new way to *build* a comparator, not a
change to what a comparator means. The bool-rejection requirement is likewise
unaffected: a key extractor returns a key, never a comparison sign, so there is
no `bool <: int` hazard on that path to guard against.

## Impact

- `src/snakestream/comparator.py` — new `comparing()` factory and the object it
  returns. This module already holds the comparator *semantics* shared by
  sorting and the min/max terminals, which is where a comparator factory
  belongs; `sort.py` holds sorting *algorithms* and would be the wrong home.
- `src/snakestream/sort.py` — new key fast path in `sort()`, ahead of the
  existing async/sync comparator dispatch.
- `src/snakestream/type.py` — an alias for the key-extractor callable, per the
  project's rule that composite/callable types live there.
- `src/snakestream/__init__.py` — export decision for the new public name.
- `README.md` — new API surface to record. Note that the parity tables today
  track `Stream` and `Collectors`; `java.util.Comparator` is a third interface
  with no table yet, so one is needed.
- No dependency, executor, sink-protocol or ordering-characteristic changes.
