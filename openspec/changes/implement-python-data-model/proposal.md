## Why

`Stream` implements **no** dunder methods at all — not `__aiter__`, not `__repr__`, nothing:

```
repr(s)                 -> <snakestream.stream.Stream object at 0x7a17...>
async for x in stream   -> TypeError: requires an object with __aiter__
a + b                   -> TypeError: unsupported operand type(s) for +
with stream as s:       -> TypeError: does not support the context manager protocol
```

The library's guiding principle is Java's API surface with Python's capabilities underneath. Satisfying Python's own protocols is the part of that which was never done, and most of the candidate set is not an expansion of the surface but a *parity gap*: Java's stream satisfies its language's iteration and resource protocols, and ours does not satisfy Python's equivalents.

The async-first design does the filtering. Protocols that demand a value synchronously — `__len__`, `__iter__`, `__contains__`, `__eq__`, `__reversed__` — cannot be implemented at all, because every terminal here is `async def`. Two of those have wrong defaults that cannot be opted out of:

- `bool(Stream.empty())` is `True`. Silently. `if stream:` is always true, including for an empty stream. This is the one place the library must *define* a dunder in order to close a hole rather than open one.
- `for x in stream` fails loudly today, which is fine — but only while no `__getitem__` exists. Python's legacy iteration protocol synthesizes an iterator from `__getitem__` when `__iter__` is absent (verified on 3.14), so adding slice support would make `for x in stream` start "working" by calling `stream[0]`, getting a `Stream` back, and looping forever. `__getitem__` is therefore **not** in this change; `.skip(10).limit(10)` is what Java says and is clearer than `s[10:20]` anyway.

## What Changes

Three of these are parity, one is a deliberate expansion, one closes a footgun.

- **`__aiter__` — parity.** `async for x in stream` becomes equivalent to `async for x in stream.iterator()`. Java's `BaseStream` exposes `iterator()` and its streams are iterable through the language's own protocol; ours makes the caller wire it up by hand. `iterator()` already returns an `AsyncGenerator`, so this is an alias, and it inherits `iterator()`'s contract wholesale — including its `observes_order=True` declaration and its non-destructive composition.
- **`__enter__` / `__exit__` — parity.** `BaseStream extends AutoCloseable`, and Java's stream is the resource in try-with-resources with no wrapper. CLAUDE.md documents pairing ours with `contextlib.closing()`, which is a workaround for two missing methods. `__exit__` calls `close()`, so every `stream-close-handling` rule applies unchanged.
- **`__repr__` — parity.** Java has `toString()`. Shows source, queued chain and executor. Pure debugging win, zero semantics.
- **`__bool__` — closes a footgun.** Raises `TypeError` rather than returning the always-`True` default. This is the first place the library refuses something Python allows on every other object, and it is deliberate: a silently-wrong answer is worse than a loud refusal, and there is no correct synchronous answer available.
- **`__add__` — expansion.** `a + b` is `Stream.concat(a, b)`. This is the only member of the set with no Java analogue and it is argued as an exception rather than smuggled in with the others: `Stream.concat` remains the contract and is unchanged, `a + b` is a Python-native alias over it, and no behaviour diverges. It inherits everything `concat()` decides, including operand invalidation.

`__copy__` is deliberately **not** here — it is `derive-without-reinit`'s to settle, since that change is what makes it load-bearing.

`__aenter__` / `__aexit__` are deliberately **not** here and are parked in the roadmap's **Later**. `CloseHandler` is a sync no-arg callable and `close()` never awaits, so `with` is the honest protocol for the close-handler contract as it stands; async cleanup is a larger question about that contract, not about this one's two methods.

## Capabilities

### New Capabilities

- `python-data-model`: which of Python's data-model protocols `Stream` implements, which it deliberately refuses, and why the refusals are refusals rather than gaps. Holds `__aiter__`, `__enter__`/`__exit__`, `__repr__`, `__bool__` and `__add__`, and records `__len__`/`__iter__`/`__contains__`/`__getitem__` as excluded with their reasons, so a later reader finds a decision rather than a silence.

### Modified Capabilities

None. `stream-iterator` and `stream-close-handling` keep their requirements exactly as they stand — `__aiter__` and `__exit__` delegate to `iterator()` and `close()` rather than restating or altering what those do. The new capability references them.

## Impact

- `src/snakestream/stream.py` — five dunder methods, all thin.
- CLAUDE.md's AutoClose section, which currently names `contextlib.closing()` as the idiom.
- README's parity tables, which are declared total over Java 8's surface: dunders are not Java methods and need a stated place in that scheme rather than becoming invisible rows.
- **Depends on `concat-carries-characteristics`.** `__add__` is sugar over `concat()`; landing it first would ship an operator that drops its operands' executor and ordering.
