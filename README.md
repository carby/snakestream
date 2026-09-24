<p align="center">
  <img src="https://raw.githubusercontent.com/carby/snakestream/master/logo.png" alt="Snakestream" width="660">
</p>


Snakestream is a [Java 8 Stream](https://docs.oracle.com/javase/8/docs/api/java/util/stream/Stream.html)-style
API for Python, built from the ground up on `async`/`await`. Chain `map`, `filter`, `sorted`,
`flat_map`, `distinct` and friends into a lazy pipeline, hand every one of them a **sync or an async**
function interchangeably, and `await` a terminal operation to run it.

```python
names = await (
    Stream(user_ids)
    .parallel()
    .map(fetch_user)  # async def — awaited for you, concurrently
    .filter(lambda u: u.active)
    .map(lambda u: u.name)  # plain def — same chain, no ceremony
    .collect(to_list())
)
```

## Install

```bash
pip install snakestream     # or: uv add snakestream
```

Python 3.14+.

> [!NOTE]
> This library is under development and has not reached version 1.0 yet. Backwards
> compatibility can still be broken — every break is listed in [CHANGELOG.md](CHANGELOG.md).

## Quick start

```python
import asyncio
from snakestream import Stream
from snakestream.collectors import to_list


async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.05)  # pretend this is a network call
    return {"id": user_id, "name": f"user-{user_id}", "active": user_id != 3}


async def main() -> None:
    names = await (
        Stream([1, 2, 3, 4, 5])
        .parallel()
        .map(fetch_user)
        .filter(lambda u: u["active"])
        .map(lambda u: u["name"])
        .collect(to_list())
    )
    print(names)  # ['user-1', 'user-2', 'user-4', 'user-5']


asyncio.run(main())
```

The five fetches overlap, and the result still comes back in encounter order.

## Why Snakestream?

**Async and sync callables are interchangeable, everywhere.** Every user-supplied function —
predicate, mapper, comparator, consumer, collector part, close handler — may be `def` or
`async def`. You never wrap, never `gather`, never think about it. Awaitability is classified
once per callable, not once per element.

**Nothing runs until you ask for a value.** Intermediate operations queue work and return a new
stream; a terminal operation drives it. Sources stay lazy all the way through, so an infinite
generator with a `.limit(10)` downstream pulls ten elements.

```python
stream = Stream(count()).map(expensive).filter(is_valid)  # nothing has run yet
first_ten = await stream.limit(10).collect(to_list())  # exactly ten pulls
```

**`.parallel()` is one word and it applies to the whole pipeline.** Contiguous batches of
elements are dispatched onto their own OS threads, each batch racing its own elements
concurrently. I/O-bound pipelines speed up on any interpreter; CPU-bound ones speed up for real
on the free-threaded build (3.14t). Switch back with `.sequential()`. See
[About `.parallel()`](#about-parallel).

**It breaks apart nested comprehensions.** A fluent chain reads top-to-bottom, and adding a
step in the middle is one line rather than a re-nesting.

```python
by_team = await Stream(users).collect(grouping_by(lambda u: u.team, counting()))
roster = await Stream(users).sorted(comparing(lambda u: u.name)).map(str).collect(joining(", "))
```

**The API is Java's, deliberately.** If you know `Stream`, `Collectors` and `Comparator` from
Java 8, you already know this library — same method names, same semantics, same ordering
guarantees. The [API tables](#api) below are *total* over Java 8's surface: every method has a
row saying implemented, skipped-and-why, or not-yet.

**It is pure Python with zero dependencies.**

## Features

- Create a stream from a List, Generator, AsyncGenerator, Iterator, AsyncIterator or just an object
- Process your stream with both synchronous and asynchronous functions
- Switch between parallel and sequential mode ([real parallelism on the free-threaded build](#about-parallel))
- Encounter order preserved under `.parallel()`, or opt out with `unordered()` for more throughput
- ~20 [collectors](#collectors) and a composable [`comparator`](#comparator), both mirroring Java
- [Autoclose](#auto-close) streams with `with`, `async with` or `contextlib`
- [Pythonic protocols](#pythons-data-model) on top of the Java surface: `async for`, `with`, `a + b`
- Generate indefinite streams [simpler than in Java](#the-generate-function)

## Scope

This is a Python streaming API that brings over the feature set Java 8 introduced with its
streams API. Once we reach some sort of feature parity with Java 8, maybe we move on to the
improvements in Java 9. There will never be *complete* parity, because the languages differ:
we don't really speak about arrays in Python, we use lists and sets; and where Java streams
lean on functional interfaces, Python is already a functional language, so `Supplier`s,
`Consumer`s and all of that are just regular functions here. So that's the road map as of now —
we get as close as we can with a reasonable effort put into it.

## Building a stream from a source

`Stream(source)` is the normalizing constructor and the idiomatic way to build a stream from something you already have: a `List`, `Generator`, `AsyncGenerator`, `Iterator`, `AsyncIterator`, or a bare object. It spreads any of those into one element per item — `Stream([1, 2, 3])` is a stream of three elements — while `dict`, `str`, `bytes`, `bytearray` and `memoryview` values, and anything with neither `__iter__` nor `__next__`, are treated as a single scalar element instead. It is the same constructor every `Stream(...)` call in this README uses, called out here because it has no counterpart in the parity tables that follow.

That absence is deliberate rather than an oversight. The tables are total over `Stream`, `BaseStream`, `Collectors` and `Comparator`, and `Stream(source)` is none of those — its closest Java counterparts, `Collection.stream()` and `Arrays.stream(T[])`, are methods on types this library does not have. `Stream.of(*args: T)` in the table below is the true parity row: it matches Java's `of(T...)` exactly, treating every argument as one element regardless of arity. Spreading a single iterable's items - what `Stream.of()` did through 0.3.5 - is `Stream(source)`, not `Stream.of(source)`.

### The generate() function

Java's `Stream.generate(supplier)` is omitted here, because Python already has generators — pass one straight to `Stream(...)` and it becomes the source:

```python
from itertools import count

first_ten_squares = await Stream(count()).map(lambda n: n * n).limit(10).collect(to_list())
```

## About `.parallel()`

Unlike Java's `parallelStream()`, snakestream's `.parallel()` does not use a process pool — there is no pickling boundary to cross, since a `Spliterator` decomposes the stream's own composed chain into batches that run in-process. But it does now run on separate OS threads: a `.parallel()` pipeline dispatches contiguous batches of elements via `asyncio.to_thread`, each batch running its own copy of the chain on its own thread, rather than racing `asyncio` tasks cooperatively over a shared generator on one thread the way it used to.

Whether that buys CPU-bound work a real speedup depends on the interpreter build. On the ordinary GIL-enabled build, only one thread runs Python bytecode at a time, so CPU-bound work sees the same result as before — no measurable speedup, confirmed at ~1.0x — aside from the usual GIL release during I/O and certain C-extension calls. On the free-threaded build (3.14t, PEP 779) there is no GIL, so batches genuinely run Python code in parallel and CPU-bound work benefits for real — measured at ~2x on a large-enough source, and small sources benefit too: a 200-element source measures ~2.0x-2.1x and an 800-element one ~1.2x-1.3x, since the batch-size ramp no longer drains a small source's remainder into a single worker's second batch the way a one-step jump to the steady-state batch size used to — see `benchmark-findings.md` in `openspec/changes/spread-small-sources-across-workers` for the figures and `parallel-worker-utilisation` (`openspec/specs/`) for the distribution guarantee itself. I/O-bound work (e.g. a mapper that awaits a network call) benefits on both builds and at any size, since it always did — measured at up to 54x in the same benchmark. See `benchmark-findings.md` in `openspec/changes/archive/2026-09-04-fork-join-executor-and-spliterator` for the numbers behind all of this.

We know `.concurrent()`/`CONCURRENCY` would be the more idiomatic name for what this used to do, but keeping `.parallel()`/`WORKERS` turned out to be the right call for a different reason than originally planned — the naming didn't need to survive a future switch to multiprocessing, it needed to survive a switch to threads.

*Where* the switch is written is Java's rule exactly: the mode belongs to the pipeline rather than to a stage, so `.map(f).parallel()` and `.parallel().map(f)` build the same thing and the last switch before the terminal governs the whole chain. What diverges is the **receiver**. Java's `parallel()` writes the flag onto the pipeline's source stage and returns `this`, so the reference you called it on *is* the returned stream and keeps working under the new mode:

```java
Stream<T> s = list.stream();
Stream<T> p = s.parallel();   // s == p, and s still usable
```

Here it returns a new stream and consumes the receiver, so the second line leaves `s` raising `IllegalStateException`. That is the same derive-and-consume rule `map()`, `filter()` and every other intermediate operation follow, applied to mode switches as well — Java can return `this` only because the flag is mutable state on a stage, and this library keeps no mutable per-stream state to flip. Assign the result and use that:

```python
s = Stream([1, 2, 3]).parallel()
count = await s.map(fetch).count()
```

## Auto Close

`Stream` is Java's `AutoCloseable` and Python's context manager at once, so `with` on the
stream directly runs whatever you registered with `on_close()`:

```python
with Stream(rows) as stream:
    letters = await stream.map(to_letter).distinct().collect(to_list())
```

`contextlib.closing()` works too, and is what older examples use — it only needs a `.close()`
attribute, which `Stream` has:

```python
from contextlib import closing

with closing(Stream(rows)) as stream:
    letters = await stream.map(to_letter).distinct().collect(to_list())
```

This is especially useful when you subclass `Stream` to wrap something IO-like that holds a
resource needing release after the stream: put that logic behind `on_close()` and the `with`
handles the rest.

A close handler may be sync or async — `on_close()` accepts either. `close()` stays synchronous: it runs sync handlers and refuses one whose result is awaitable, raising `StreamBuildException` and pointing you at `aclose()`/`async with`. `aclose()` is the asynchronous twin — it awaits an awaitable handler's result and runs a sync handler exactly as `close()` does, one at a time, in registration order:

```python
stream = Stream(rows).on_close(conn.aclose)

async with stream as s:
    it = await s.map(parse).collect(to_list())
```

`contextlib.aclosing()` works the same way `contextlib.closing()` does, for the same reason — `Stream` implements `__aenter__`/`__aexit__` beside `__enter__`/`__exit__`. Use `with`/`closing()` when every handler is sync; reach for `async with`/`aclosing()` only once a handler needs awaiting.

Your subclass's `__init__` runs **once per pipeline** — at your own `MyStream(...)` call, not again for each `.map()` or `.parallel()` — so a resource you acquire there is acquired once and shared by every stage, and the one `close()` releases it once. Your `__init__` may also take whatever arguments you like; nothing requires it to mirror `Stream.__init__`:

```python
class DsnStream(Stream):
    def __init__(self, dsn):
        self.conn = connect(dsn)
        super().__init__(self.conn.rows())
        self.on_close(self.conn.close)


with closing(DsnStream("db://x")) as stream:
    rows = await stream.map(parse).filter(is_valid).collect(to_list())
```

## Python's data model

The parity tables below are total over Java 8's surface, and Python's dunder methods are not Java methods — so they live here rather than becoming rows nobody wrote.

Three of these are parity rather than expansion: Java's stream satisfies its own language's iteration, resource and `toString` protocols, and these are Python's equivalents.

| | Protocol | Notes |
| ---- | ------------------------- | ---- |
| x | `__aiter__` | `async for element in stream`, exactly equivalent to iterating `stream.iterator()` — same laziness, same encounter-order guarantee, same `IllegalStateException` on an extended reference. |
| x | `__enter__` / `__exit__` | `with stream as s:` calls `close()` on exit and suppresses nothing. Java's `BaseStream` extends `AutoCloseable`; this is the same thing without the `contextlib.closing()` wrapper. |
| x | `__aenter__` / `__aexit__` | `async with stream as s:` awaits `aclose()` on exit and suppresses nothing, mirroring `__enter__`/`__exit__`. No Java counterpart — Java has no asynchronous streams. Makes `contextlib.aclosing(stream)` work the same way `__enter__`/`__exit__` make `contextlib.closing(stream)` work. |
| x | `__repr__` | `<Stream [map, filter] parallel>` — type, queued chain and mode. Pulls nothing and never raises, whatever state the stream is in. The source is deliberately not shown. |
| x | `__add__` | `a + b` is `Stream.concat(a, b)` and nothing more, so everything concat decides — mode, ordering, handlers, operand invalidation — is decided there. **The one addition with no Java counterpart.** A non-`Stream` operand raises `TypeError` rather than being coerced. |
| x | `__bool__` | **Raises `TypeError`.** Whether a stream is empty can only be answered by consuming it, and consumption is async, so there is no correct synchronous answer — and without this, `object.__bool__` makes every stream truthy, an empty one included. Await `count()`, `any_match(...)` or `find_any()` instead. |
|   | ~~`__len__`~~ | Refused. Needs a value synchronously; `count()` is a coroutine. |
|   | ~~`__iter__`~~ | Refused. Synchronous iteration cannot drive an async pipeline; use `async for`. |
|   | ~~`__contains__`~~ | Refused. `await stream.any_match(lambda x: x == target)` is the async form. |
|   | ~~`__getitem__`~~ | Refused, and the one that could have worked — `s[10:20]` is lazy. Python synthesizes an iterator from `__getitem__` when `__iter__` is absent, so defining it would make `for x in stream` call `stream[0]`, get a `Stream` back, and loop forever. `.skip(10).limit(10)` is what Java offers and is clearer. |
|   | ~~`__reversed__`~~ | Refused. A stream has no length and is single-pass. |
|   | ~~`__eq__`~~ | Refused; identity comparison stands. Comparing contents would mean consuming both. |

## API

The three tables below are **total over Java 8's surface**: every method of
`Stream`, `BaseStream`, `Collectors` and `Comparator` has a row, whether or not
it exists here. A Java 8 method with no row is a defect in the table, not a
silence to interpret. The leftmost column has three states:

| Column | Row | Meaning |
| ------ | --- | ------- |
| `x` | `name(...)` | Implemented. |
| | ~~`name(...)`~~ | Deliberately skipped. The summary says why. |
| | `name(...)` | Not yet implemented, and a genuine parity gap. The summary says what it would take and points at its `roadmap/` entry. |

The tables cover `Stream` and `BaseStream` only. `IntStream`, `LongStream` and
`DoubleStream` are skipped wholesale, for the reason `map_to_int()`'s row below
gives: they exist in Java to avoid autoboxing primitives and to expose
numeric-only operations a generic `Stream<T>` cannot offer, and Python numbers
are already objects with no boxing cost. Every primitive-specialization skip row
in the tables is a consequence of that one decision rather than an independent
judgement.

`StreamSupport` is skipped too, but only six of its eight statics fall to that
same reason — the `intStream`/`longStream`/`doubleStream` pairs. The two generic
`stream(Spliterator, boolean)` overloads do not, and they are the ones that turn
a `Spliterator` back into a stream. `spliterator()` exists here and that return
trip does not, which is a real gap rather than a primitive-specialization
consequence; it is tracked in [`roadmap/`](roadmap/) as `spliterator-round-trip`
rather than settled here.

### Stream

| done | function                        | returns                     | type     | summary                                                                                 |
| ---- | ------------------------------- | --------------------------- | ---------|---------------------------------------------------------------------------------------- |
| x | all_match(predicate: Predicate) | bool                        | instance | Returns whether all elements of this stream match the provided predicate                |
| x | aclose() | None (awaited) | instance | The asynchronous twin of `close()`. No Java counterpart. Runs every handler registered with `on_close()`, in registration order, one at a time, awaiting a handler's result where it is awaitable - a sync-only handler list behaves exactly as under `close()`. Carries `close()`'s failure contract unchanged and never touches the stream's source. Pair it with `contextlib.aclosing()` or `async with`; see [Auto Close](#auto-close). |
| x | any_match(predicate: Predicate) | bool                        | instance | Returns whether any elements of this stream match the provided predicate                |
| x | builder()                       | StreamBuilder               | static   | Returns a builder for a Stream                                                          |
| x | close() | None | instance | Runs every handler registered with `on_close()`, in registration order - Java's `BaseStream.close()`. Handlers are plain no-arg callables or coroutines, not stream-aware. A raising handler does not abort the rest: every handler runs, and the first exception is re-raised afterwards with the others attached to it as notes on Python 3.11+. `close()` stays synchronous and refuses a handler whose result is awaitable, raising `StreamBuildException` and pointing at `aclose()`/`async with` rather than leaving an un-awaited coroutine behind. Pair it with `contextlib.closing()` rather than calling it by hand; see [Auto Close](#auto-close). |
| x | collect(collector: Collector)    | R (awaited) | instance | Performs a mutable reduction operation on the elements of this stream using a `Collector` (see the Collectors section below), returning something to `await`. Passing anything else raises `StreamBuildException`; a caller wanting a lazy, streaming handle uses `iterator()` instead. |
| x | collect(supplier: Supplier, accumulator: BiConsumer, combiner: BiConsumer) | R | instance | Performs a mutable reduction on the elements of this stream: `supplier` creates the result container, `accumulator` folds each element into it. Under `.parallel()`, where the source spans more than one batch, `combiner` merges each batch's independently accumulated container into the next, on the same contiguous-batch decomposition `spliterator()` provides; under `.sequential()` it is never invoked, since there is only ever one container. `combiner` is a `BiConsumer<R,R>`, matching Java's own `Stream.collect(Supplier, BiConsumer, BiConsumer)` exactly: it may mutate its first argument and return nothing (`list.extend`, matching Java's documented `List::addAll` example), or return the merged container explicitly - both are accepted. It is understood to be associative; see the Collectors section below and `roadmap/`. |
| x | concat(a: Stream, b: Stream)    | Stream                      | static   | Creates a lazily concatenated stream whose elements are all the elements of the first stream followed by all the elements of the second stream |
| x | count()                         | int                         | instance | Returns the count of elements in this stream                                            |
| x | distinct()                      | Stream                      | instance | Returns a stream consisting of the distinct elements (using ==) of this stream. On an ordered pipeline the survivor of each equal group is the earliest in encounter order, under `parallel()` as well as sequentially; on one declared `unordered()` it is an arbitrary representative          |
| x | empty()                         | Stream                      | static   | Returns an empty sequential Stream                                                      |
| x | filter(predicate: Predicate)    | Stream                      | instance | Returns a stream consisting of the elements of this stream that match the given predicate |
| x | find_any()                      | T \| None                  | instance | Returns some element of the stream, or `None` if the stream is empty |
| x | find_first()                    | T \| None                   | instance | Returns the first element of the stream in encounter order, or `None` if the stream is empty. Preserves encounter order whatever executor the stream carries and whether or not it is ordered — matching Java, whose `findFirst()` finds the leftmost element on an unordered parallel stream too. It runs under the stream's own executor while doing so, like Java's `FindTask`, so a `parallel()` chain still runs concurrently and a dropping head (`filter`, `flat_map`) is measurably faster there; the cost is that a chain callable may run for more than one element. Use `find_any()` for the unordered alternative |
| x | flat_map(flat_mapper: FlatMapper) | Stream                    | instance | Returns a stream consisting of the results of replacing each element of this stream with the contents of a mapped stream produced by applying the provided mapping function to each element |
|   | ~~flat_map_to_double(flat_mapper: FlatMapper)~~ | Stream    | instance | Not relevant. Exists in Java to avoid autoboxing `double`s and to expose numeric-only ops (`sum()`, `average()`) that a generic `Stream<T>` can't offer. Python numbers are already objects with no boxing cost, and `sum()`/`min()`/`max()` work on any iterable, so there's no equivalent problem to solve. | 
|   | ~~flat_map_to_int(flat_mapper: FlatMapper)~~ | Stream       | instance | Not relevant, same reasoning as `flat_map_to_double`. | 
|   | ~~flat_map_to_long(flat_mapper: FlatMapper)~~ | Stream      | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. | 
| x | for_each(consumer: Callable[T]) | Any                         | instance | Performs an action for each element of this stream | 
| x | for_each_ordered(consumer: Callable[T]) | Any               | instance | Performs an action for each element of this stream, in the encounter order of the stream if the stream has a defined encounter order. A pipeline on which `unordered()` is in effect has none, so there it is equivalent to `for_each()`. Both cases run under the stream's own executor: an ordered `parallel()` pipeline still races every operation and only the invocation of `consumer` is ordered, so an operation queued *upstream* of this one is not ordered by it | 
|   | ~~generate(supplier: Callable[T])~~           | Stream        | static   | Not relevant. We can send in generators directly as a `Stream(...)` source already|
|   | ~~is_ordered()~~ | bool | instance | Not relevant. Java exposes exactly one piece of pipeline introspection, `isParallel()`; the ordering characteristic lives in the package-private `StreamOpFlag.ORDERED` and is never readable by a caller. A caller influences ordering through `unordered()` and `sorted()`, and observes it through what the order-sensitive terminals do — so there is no accessor to be at parity with. Was public through 0.3.5; see the migration log. |
| x | is_parallel() | bool | instance | Returns whether this stream, if a terminal operation were to be executed, would execute in parallel |
| x | iterate(seed: T, nxt: Mapper[T, T]) | Stream | static | Returns an infinite sequential ordered Stream produced by iterative application of a function f to an initial element seed, producing a Stream consisting of seed, f(seed), f(f(seed)), etc. `nxt` may be sync or async, like every other user-supplied callable. |
| x | iterator() | AsyncGenerator | instance | Composes the current chain and returns the resulting async generator directly, without consuming it, so the caller can drive iteration themselves. It hands out raw elements, so the order they arrive in is observable: on an ordered `parallel()` stream it yields in encounter order, and on one declared `unordered()` it yields as batches finish |
| x | limit(max_size: int)                    | Stream | instance | Returns a stream consisting of the elements of this stream, truncated to be no longer than max_size() in length. On an ordered pipeline these are the first `max_size` in encounter order, under `parallel()` as well as sequentially; on one declared `unordered()` they are the first to arrive, as in Java. |
| x | map(mapper: Mapper)                     | Stream | instance | Returns a stream consisting of the results of applying the given function to the elements of this stream. |
|   | ~~map_to_double(mapper: ToDoubleMapper)~~  | Stream | instance | Not relevant, same reasoning as `flat_map_to_double`. |
|   | ~~map_to_int(mapper: ToIntMapper)~~       | Stream | instance | Not relevant, same reasoning as `flat_map_to_double`. |
|   | ~~map_to_long(mapper: ToLongMapper)~~   | Stream | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. |
| x | max(comparator: Comparator)             | T \| None | instance | Returns the maximum element of this stream according to the provided Comparator, or `None` if the stream is empty. Of two elements that compare equal the first in **encounter order** wins, on an ordered pipeline under `parallel()` as well as sequentially — so the answer matches the sequential one. On a pipeline declared `unordered()` which of two tied elements is returned is unspecified, as in Java; supply a total comparator (`comparing(k).then_comparing(t)`) if you need determinism without the ordering barrier. |
| x | min(comparator: Comparator)             | T \| None | instance | Returns the minimum element of this stream according to the provided Comparator, or `None` if the stream is empty. Same tie-break rule as `max()` above. |
| x | none_match(predicate: Predicate)        | bool | instance | Returns whether no elements of this stream match the provided predicate. |
| x | of(*args: T)                            | Stream | static | Returns a sequential ordered stream whose elements are the specified values, matching Java's `of(T...)`: every argument is one element, atomically, whatever its arity — `Stream.of([1, 2, 3])` is a stream of one element, the list. See [Building a stream from a source](#building-a-stream-from-a-source) for spreading a single iterable into its items. |
| x | on_close(close_handler: CloseHandler) | Stream | instance | Registers a callable to run when `close()`/`aclose()` is called, matching Java's `BaseStream.onClose()`. `close_handler` may be sync or async - registration does not inspect or classify it; which closer can run it is decided at close time. Unlike every intermediate operation, this mutates the receiver and returns it, and works on a consumed reference. The handler list is shared across every stage derived from one source, so one `close()`/`aclose()` releases the resource once. |
|   | ~~ordered()~~   | Stream   | instance | Does not exist in Java, and so is not missing here. Ordering is not something a caller turns on: it is a spliterator characteristic (`ORDERED`) contributed by the **source** — every snakestream source constructor (`Stream(...)`, `Stream.of()`, `iterate()`) produces an ordered stream, as `Stream.of()`, a `List` and `iterate()` do in Java — and from there it is only ever cleared by `unordered()` (`NOT_ORDERED`) or re-imposed by an op that defines an order, `sorted()` (`IS_ORDERED`). `BaseStream` therefore has `unordered()` and no counterpart, and `sorted()` already covers restoring what `unordered()` cleared. |
| x | parallel()     | Stream   | instance | Returns an equivalent stream that will execute in parallel. Applies to the **whole** pipeline, not only the operations declared after it, matching Java; the last mode switch before a terminal operation is the one that governs. **Consumes the receiver**, unlike Java's `parallel()`, which sets a flag on the source stage and returns `this` — use the returned stream, since the one it was called on now raises `IllegalStateException` ([see above](#about-parallel)). An ordered pipeline still delivers in encounter order: every operation runs concurrently across batches and only the handing of finished elements to the terminal is put back in order, as in Java. An operation that depends on position (`sorted`, `limit`, `skip`, `distinct`) likewise gets encounter order where the pipeline is ordered at that operation. Declaring `unordered()` opts out of both and is the faster path; terminals that observe nothing about order (`count()`, `for_each()`, `find_any()`, the `*_match()` family) pay nothing either way. `max()`/`min()` do observe it — their *value* is the same in any order but which of two tied elements they return is not — so on an ordered pipeline they take the delivery barrier too, and `unordered()` releases them from it |
| x | peek(self, consumer: Consumer)          | Stream | instance | Returns a stream consisting of the elements of this stream, additionally performing the provided action on each element as elements are consumed from the resulting stream. |
| x | reduce(identity: T \| R, accumulator: Accumulator) | T \| R | instance | Performs a reduction on the elements of this stream, using the provided identity value and an associative accumulation function, and returns the reduced value. |
| x | reduce(accumulator: BinaryOperator) | T \| None | instance | Performs a reduction on the elements of this stream, using an associative accumulation function seeded by the stream's own first element, and returns the reduced value, or None if the stream is empty. |
| x | reduce(identity: T \| R, accumulator: Accumulator, combiner: BinaryOperator) | T \| R | instance | The third of Java's three `reduce` overloads. Note that the *type widening* it carries in Java - a result type `U` distinct from the element type `T` - was already on the two-argument row above, whose `Accumulator` is `(T \| R, T) -> T \| R`; the `combiner` is the whole of what this overload adds. Under `.parallel()`, where the source spans more than one batch, `combiner` merges each batch's independently reduced partial result into the next, on the same contiguous-batch decomposition `spliterator()` provides; under `.sequential()` it is never invoked. `combiner` is understood to be associative, and `identity` an identity for it: each partition starts from `identity`, so a value that is not one contributes once per partition and the parallel result can diverge from the sequential one - the library states this as a caller contract, matching Java, and does not check it. |
| x | sequential()   | Stream   | instance | Returns an equivalent stream that will execute sequentially. Applies to the **whole** pipeline, on the same rule as `parallel()`, and consumes the receiver on the same rule too |
| x | skip(n: int)                             | Stream | instance | Returns a stream consisting of the remaining elements of this stream after discarding the first n elements of the stream. On an ordered pipeline the `n` discarded are the first `n` in encounter order, under `parallel()` as well as sequentially; on one declared `unordered()` they are the first `n` to arrive. |
| x | sorted(comparator: Comparator \| None = None, reverse: bool = False) | Stream | instance | Returns a stream consisting of the elements of this stream, sorted according to natural ordering, or according to the provided Comparator if given. Restores encounter order downstream, undoing an earlier `unordered()` — a sort imposes an order whether or not its input had one, as Java's `sorted()` does. Sorts the whole stream under `parallel()` too, not each batch's subset — and on a pipeline declared `unordered()` as well, since a sort claims its output is ordered wherever it sits. **Stable**: elements that compare equal keep the relative order they entered with, sequentially and under `parallel()` alike. `reverse=True` and a `comparing()` comparator's own `reversed()` mean different things and compose: `reverse=True` reverses the sorted buffer afterward, which also flips elements the comparator treated as equivalent; `reversed()` negates the comparator itself, which does not. |
| x | spliterator() | Spliterator | instance | Java's parallel-decomposition iterator, ported with its full method surface: `try_advance(action)`, `try_split()`, `estimate_size()`, `characteristics()`, `for_each_remaining(action)`, plus a `Characteristics` enum reporting `ORDERED`/`SIZED`. Composes the stream's chain the same way `iterator()` does, but hands back a decomposable object instead of a bare generator. `try_split()` always drains a bounded batch off the front rather than index-splitting — by the time the chain is composed the source is an `AsyncGenerator` with no random access, the same fallback Java's own `Spliterators.IteratorSpliterator` takes for an unsized source. This is what `.parallel()` is now built on internally (`execution.py`'s fork-join executor uses the same bounded-drain primitive `try_split()` does), and is also directly usable by a caller who wants manual decomposition. |
| x | to_array()                              | List[T] | instance | Returns a list containing the elements of this stream. Equivalent to `collect(to_list())`; Java's `toArray()` returns an array, but Python has no distinct array type competing with `list`. |
|   | ~~toArray(generator: IntFunction[Array[T]])~~ | Array[T] | instance | Not relevant. Exists in Java to work around the lack of runtime generic-array construction, letting callers get a correctly-typed array instead of `Object[]`. Python's `list` has no array/generic-array distinction to work around, so there's no equivalent problem for this overload to solve. |
| x | unordered()    | Stream   | instance | Marks the pipeline as not order-dependent **from this point downstream** — operations queued before it are unaffected, as in Java, where `unordered()` is a pipeline stage rather than a flag on the source. A later `sorted()` restores it. Position-dependent, unlike `parallel()`/`sequential()`, and survives a mode switch because the chain does. Under `parallel()` it is a performance lever and not only a semantic one, and is the primary way to buy concurrency back: an ordered pipeline holds a finished element until every earlier one has been released — for a position-dependent operation *and* for delivery to a terminal that observes order — and declaring it unordered removes both |
|   | ~~Optional~~ | Optional<T> | type | Skipped, and the reason is that Python already has the half of it that matters. `find_first()`, `find_any()`, `max()`, `min()` and the no-identity `reduce()` return `T \| None`, and `is None` answers the membership question `isPresent()` answers in a language where the alternative is a `null` the type system cannot see. The chaining half - `map`, `flat_map`, `if_present`, `or_else_get` - is a second fluent API layered on the first, and a caller who wants it can build it over the value they already hold. Implementing it would be a new public type plus a return-type break on four terminals and `reduce()`, so if it is ever wanted it deserves its own proposal rather than a place in the parity queue. |

### Collectors

`Collector` lives in `snakestream.collector`; every factory in the table below lives in `snakestream.collectors`, the same split Java draws between the `Collector` interface and the `Collectors` class that holds the factories.

`Collector(supplier, accumulator, combiner=None, finisher=None, characteristics=frozenset())` is the type every factory below returns, mirroring Java's `Collector<T,A,R>`: `supplier()` creates a fresh accumulation container, `accumulator(container, element)` mutates it per element (sync or async; its return value is ignored), and `finisher(container)` converts the finished container into the result, or the container itself is the result if `finisher` is omitted. `combiner(container, container)` merges two partial containers into one, left-biased in batch order, and is invoked under `.parallel()` wherever the collector supplies one and the source spans more than one batch (`parallel-reduction`); a collector with no `combiner` is never partitioned, and folds into a single container exactly as every collector did before this. `characteristics` is a `Characteristics` set - data, not a callable, so it is neither invoked nor awaited - defaulting to empty, so every existing `Collector(...)` call is unaffected. A `Collector` instance holds no other per-collection state, so the instance one of these factories returns is safe to reuse across streams and across concurrent collections. You can construct one directly for a custom reduction: `Stream([1, 2, 3]).collect(Collector(list, lambda c, e: c.append(e)))`.

`characteristics` is a declaration a collector makes about itself, not an instruction any operation performs. `collect()` is its only reader: under `parallel()` it reads `UNORDERED` to decide whether the collector is owed a reorder barrier. `UNORDERED` promises that any two orderings of the same elements collect to an **equal** result - `==` on the result's own type - and promises nothing about the iteration order of that result.

| done | function                                              | returns   | type    | summary                                                                 |
| ---- | ------------------------------------------------------ | --------- | ------- | ------------------------------------------------------------------------ |
| x | joining(delimiter: str = "", prefix: str = "", suffix: str = "") | Collector | factory | Returns a collector, for use with `collect()`, that concatenates the stream's `str` elements, separated by `delimiter` and wrapped in `prefix`/`suffix`. |
| x | counting() | Collector | factory | Returns a collector, for use with `collect()`, that counts the stream's elements as an `int`. Declares `UNORDERED`, so under `parallel()` it is fed as the race resolves elements rather than in encounter order. |
| x | summing_int(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and sums the results as an `int`. Declares `UNORDERED`, so under `parallel()` it is fed as the race resolves elements rather than in encounter order. |
| x | summing_long(mapper) | Collector | factory | Same as `summing_int`, `UNORDERED` included; kept as a separate name for parity with Java's `summingLong`, since Python has no `int`/`long` distinction. |
| x | summing_double(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and sums the results as a `float`. Does not declare `UNORDERED` and never will: float addition is not associative, so two orderings of the same elements can sum to values that compare unequal. It is fed in encounter order under `parallel()`. |
| x | averaging_int(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and returns the arithmetic mean as a `float` (`0.0` for an empty stream). Does not declare `UNORDERED` and never will: it divides a float accumulator, so it is order-sensitive in fact, `averaging_int` and `averaging_long` included despite their `int` inputs. |
| x | averaging_long(mapper) | Collector | factory | Same as `averaging_int`; kept as a separate name for parity with Java's `averagingLong`. |
| x | averaging_double(mapper) | Collector | factory | Same as `averaging_int`; kept as a separate name for parity with Java's `averagingDouble`. |
| x | summarizing_int(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and finishes to a `SummaryStatistics` (`count`, `sum`, `min`, `max`, `average`) over the mapped `int` values; `min`/`max` are `None` for an empty stream. Declares `UNORDERED`, so under `parallel()` it is fed as the race resolves elements rather than in encounter order. Every field is order-invariant over `int` inputs: `min`/`max` select a *value*, not an element, so unlike `min_by`/`max_by` there is no tie identity to preserve. |
| x | summarizing_long(mapper) | Collector | factory | Same as `summarizing_int`, `UNORDERED` included; kept as a separate name for parity with Java's `summarizingLong`. |
| x | summarizing_double(mapper) | Collector | factory | Same as `summarizing_int`, but coerces the mapped values and the resulting `sum`/`min`/`max` to `float`. Does not declare `UNORDERED` and never will: its `sum` accumulates in float, and `SummaryStatistics` compares by value across every field, so that one field decides the whole result. |
| x | min_by(comparator) | Collector | factory | Returns a collector, for use with `collect()`, that selects the smallest element per the 3-way-int `comparator`, `None` for an empty stream, first-of-tied-elements wins. Shares the comparator-contract check and the first-of-tied rule with `Stream.min()` rather than reimplementing them. |
| x | max_by(comparator) | Collector | factory | Same as `min_by`, but selects the largest element, sharing the same rule with `Stream.max()`. |
| x | reducing(binary_operator) / reducing(identity, binary_operator) / reducing(identity, mapper, binary_operator) | Collector | factory | Returns a collector that folds the stream via `binary_operator`, matching Java's three `Collectors.reducing` overloads: no-identity (seeds from the first element, `None` for an empty stream), with `identity` (returns `identity` unchanged for an empty stream), and with `identity` + `mapper` (maps each element before folding). Mirrors `Stream.reduce()`'s existing semantics. |
| x | to_map(key_mapper, value_mapper, merge_function=None) | Collector | factory | Returns a collector, for use with `collect()`, that builds a `dict` from `key_mapper`/`value_mapper` applied to each element. Raises `IllegalStateException` on a duplicate key unless `merge_function` is given, in which case the colliding values are resolved via `merge_function(existing, new)`. **The two forms declare different characteristics.** Called without `merge_function` it declares `Characteristics.UNORDERED`: the `dict` it builds is a function of the elements alone, so any two orderings of them collect to an equal result, and a parallel `collect()` owes it no reorder barrier. Called with one it declares nothing, permanently - a caller-supplied `merge_function` need not commute (`lambda a, b: a` keeps whichever value arrived first), so its result does depend on delivery order. One consequence of the mark, on the failure path: with two or more *distinct* collisions under `.parallel()`, which colliding key the `IllegalStateException` names is not guaranteed. That it raises at all is unchanged, and sequential behaviour is unchanged. |
| x | to_map(key_mapper, value_mapper, merge_function, map_supplier) | Collector | factory | Returns a collector that builds the mapping `map_supplier()` returns, instead of a plain `dict`, resolving duplicate keys via `merge_function` exactly as the three-argument form above does. `map_supplier` is called once per collection for a fresh empty mapping - sync or async, awaited like every other user-supplied callable - and that same object is returned as-is rather than copied into a `dict`, so `OrderedDict`, a `defaultdict`, or any `MutableMapping` reaches the caller intact. **There is deliberately no `to_map(key_mapper, value_mapper, map_supplier)` form.** Java has exactly three `toMap` overloads and the four-argument one requires `mergeFunction`; adding a container-only form would expand the public surface rather than close a parity gap. The exclusion is enforced by the declared `@overload` set and caught by `ty`, not by a runtime raise - "a merge function" and "a mapping type" are both callables of the right shape, so there is no honest runtime predicate for it. Because the form always carries a `merge_function`, it declares no `Characteristics.UNORDERED`, for the reason the three-argument form does not: a caller-supplied merge need not commute. The container therefore never reaches that decision here - contrast `grouping_by`'s `map_factory` row below, which does. |
| x | to_list() | Collector | factory | Returns a collector, for use with `collect()`, that builds a `list` from the stream's elements, in encounter order — on an ordered `parallel()` stream as well as a sequential one. |
| x | to_set() | Collector | factory | Returns a collector, for use with `collect()`, that builds a `set` from the stream's elements. Declares `UNORDERED`, so under `parallel()` it is fed as the race resolves elements rather than in encounter order. |
| x | to_collection(collection_supplier) | Collector | factory | Returns a collector, for use with `collect()`, that calls `collection_supplier()` once for a fresh container and adds each element to it via the container's `add` method - a generalization of `to_list`/`to_set` to any caller-supplied container type. |
| x | grouping_by(classifier, downstream: Collector = to_list()) | Collector | factory | Returns a collector, for use with `collect()`, that buckets elements by `classifier` into `dict[K, list[T]]`, or `dict[K, R]` if a `downstream` `Collector` is given to reduce each group. Only keys `classifier` actually produced appear. Each group accumulates into its own downstream container as elements arrive, rather than being buffered and replayed afterwards. Declares `UNORDERED` exactly when `downstream` does, so under `parallel()` a grouping into `to_set()` is fed as the race resolves elements while the default list downstream is fed in encounter order. `downstream` must be a `Collector`; anything else raises `StreamBuildException`. |
| x | grouping_by(classifier, map_factory, downstream: Collector) | Collector | factory | Returns a collector that buckets into the mapping `map_factory()` returns, instead of a plain `dict`, with `downstream` collecting each group exactly as in the two-argument form. `map_factory` sits in Java's own argument position, second, and is called once per collection for a fresh empty mapping (sync or async); group keys are inserted into it and each group's downstream result is finished back into it, so the caller's type is what comes out. **Existing calls are unaffected:** the form is chosen by *argument count*, never by inspecting an argument's type, so `grouping_by(f, to_list())` still binds its second argument to `downstream`. **A caller-supplied `map_factory` clears `Characteristics.UNORDERED`**, whatever `downstream` declares. The two-argument form's derivation rests on `dict` equality ignoring key insertion order, and a caller-supplied mapping type need not: an `OrderedDict` compared against another `OrderedDict` is equal only if its keys went in in the same order, and insertion order here follows the order groups were first seen - which racing reorders. The exclusion keys on `map_factory` being *supplied at all* rather than on the type it produces, so `grouping_by(f, dict, to_set())` is cleared too; a caller who knows their chosen type's equality ignores key order has `unordered()`, one level up. Same rule as `to_collection()`, which declares nothing for the same reason. |
| x | partitioning_by(predicate, downstream: Collector = to_list()) | Collector | factory | Returns a collector, for use with `collect()`, that splits elements into `dict[True/False, list[T]]` per `predicate`, or `dict[True/False, R]` if a `downstream` `Collector` is given. Both keys are always present, even if one partition is empty - both downstream containers are created up front, which is also why only the `downstream` can observe order: it declares `UNORDERED` exactly when `downstream` does. `downstream` must be a `Collector`; anything else raises `StreamBuildException`. |
| x | mapping(mapper, downstream: Collector) | Collector | factory | Returns a collector, for use with `collect()`, that applies `mapper` to each element before feeding it to `downstream`. `downstream` must be a `Collector`; anything else raises `StreamBuildException`. |
| x | collecting_and_then(downstream: Collector, finisher) | Collector | factory | Returns a collector, for use with `collect()`, that accumulates exactly as `downstream` would, then runs `downstream`'s finished result through `finisher`. `downstream` must be a `Collector`; anything else raises `StreamBuildException`. |
|   | ~~grouping_by_concurrent(...)~~ | Collector | factory | Not relevant. Java's concurrent `groupingBy` exists to let a `CONCURRENT` collector accumulate into one shared container from several threads at once, skipping the per-partition merge. `CONCURRENT` is intentionally not implemented here, for the reason the `Collector.Characteristics` row below gives: no execution mode produces independently-reduced partitions to merge, so there is nothing for the concurrent variant to avoid. |
|   | ~~to_concurrent_map(...)~~ | Collector | factory | Not relevant, same reasoning as `grouping_by_concurrent` above. |
|   | ~~Collector.of(supplier, accumulator, combiner, [finisher], characteristics)~~ | Collector | static | Not relevant. Java needs a static factory because `Collector` is an interface a caller cannot instantiate. Here it is a class: `Collector(supplier, accumulator, combiner=None, finisher=None, characteristics=frozenset())` is the constructor, documented above this table, and it takes the same five things in the same order. Nothing is missing. |
| x/- | Collector.Characteristics | enum | type | Mirrors Java's `Collector.Characteristics`. `UNORDERED` is implemented and declared by `to_set()`, `counting()`, `summing_int()`/`summing_long()` and `summarizing_int()`/`summarizing_long()`, and derived from their downstream by `mapping()`, `collecting_and_then()`, `grouping_by()` and `partitioning_by()`. The `summing_double()`/`averaging_*()`/`summarizing_double()` family declares it nowhere and never will, float addition not being associative; `min_by()`/`max_by()` do not declare it either, returning an element whose tie must break in encounter order. It promises `==`-equality of the collected result for any ordering of the same elements, and nothing about that result's iteration order. `collect()` reads it under `parallel()`: a collector declaring it is fed as the race resolves elements, and one that does not is fed in encounter order. `IDENTITY_FINISH` (already observable as `finisher is None`) and `CONCURRENT` (no execution mode here produces independently-reduced partitions to merge) are intentionally not implemented. |

### Comparator

`comparing()` lives in `snakestream.comparator`, alongside the comparator semantics `sorted()`, `min()`, `max()`, `min_by()` and `max_by()` already share.

| done | function                                 | returns    | type    | summary                                                                 |
| ---- | ----------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------ |
| x | comparing(key_extractor, key_comparator=None) | KeyComparator | factory | Returns a `KeyComparator` - itself a `Comparator` - that orders elements by a key extracted from each one, matching Java's `Comparator.comparing(keyExtractor)`. `key_extractor` may be sync or async. Accepted anywhere a `Comparator` is - `sorted()`, `min()`, `max()`, `min_by()`, `max_by()` - with no signature changes. `sort()` recognizes the value `comparing()` returns and extracts each key exactly once rather than once per comparison, which for an async extractor is the difference between O(n) and O(n log n) awaits. A hand-written tuple key (`comparing(lambda x: (x.last, x.first))`) is still the better answer for a sync, single-direction, multi-key ordering - one call per element, no wrapper object, no gather; `then_comparing()` below earns its keep once an extractor is async (a tuple literal cannot await) or directions mix. `key_comparator`, matching Java's two-argument `Comparator.comparing(keyExtractor, keyComparator)`, orders the extracted keys by that `Comparator` instead of their natural ordering - useful when the key has none - and must be synchronous, though `key_extractor` may still be async. |
| x | then_comparing(other, key_comparator=None) | KeyComparator | instance | Appends a tie-break ordering, matching Java's three `thenComparing` overloads. A chain must begin at `comparing()`. `other` may be a bare key extractor (one ascending segment), another `KeyComparator` (its whole segment list, directions intact), or a bare `Comparator` (that ordering directly, consulted only on a tie); told apart from a key extractor by counting positional parameters - one is a key extractor, two is a `Comparator` - with a `KeyComparator` recognised by type ahead of either. `key_comparator`, if given, orders the keys `other` extracts rather than their natural ordering, matching `comparing()`'s second parameter. Returns a new `KeyComparator`; the receiver is unchanged. Sorting extracts every segment's key exactly once per element, eagerly; a comparator segment is invoked directly rather than through an extracted key. A supplied comparator, bare or as `key_comparator`, must be synchronous - rejected with `StreamBuildException` at construction, naming an async key extractor segment or a bare async comparator passed straight to `sorted()` as the supported alternatives - and composes with direction, null tolerance and stability exactly as a key-based segment does. See `openspec/changes/add-comparator-segments`. |
| x | reversed() | KeyComparator | instance | Negates the ordering built so far, matching Java's `Comparator.reversed`. Reverse before chaining to flip only that segment, or after to flip the whole composite - the same distinction Java's two call sites produce. This is comparator negation, not output reversal: elements the ordering treats as equivalent keep their encounter order, unlike `sorted(comparator, reverse=True)`, which reverses the sorted buffer and so also flips tied elements. |
| x | nulls_first(comparator=None) / nulls_last(comparator=None) | Comparator | factory | Wraps a comparator so `None` sorts before (respectively after) every non-`None` value instead of raising, matching Java's `Comparator.nullsFirst`/`nullsLast`. `comparator` orders two non-`None` values and may be omitted, in which case every non-`None` value is equivalent to every other, as in Java's `nullsFirst(null)`. Also tolerates a null *extracted key*, not only a null element - a case Java reaches only through the declined `comparing(f, nullsFirst(...))` overload, closed here directly instead: an element whose key is `None` sorts as if the element itself were, and two elements with `None` keys on one segment fall through to the next. Given a `KeyComparator` (what `comparing()` returns), the result is a `KeyComparator` whose segments are null-tolerant, so `sorted()` keeps the decorate-sort-undecorate fast path; given any other `Comparator`, or none, the result is a plain wrapping comparator. Composes with `.then_comparing()` and `.reversed()` on a returned `KeyComparator`: a tie-break appended to a tolerant chain is tolerant too (a deliberate divergence from Java, which throws there instead), and reversing a nulls-first ordering places nulls last, matching Java. Accepted anywhere a `Comparator` is - `sorted()`, `min()`, `max()`, `min_by()`, `max_by()` - with no signature changes. See `openspec/changes/add-comparator-null-ordering`. |
|   | ~~naturalOrder()~~ | Comparator | static | Not relevant. `sorted()` with no comparator already is natural order. |
|   | ~~reverseOrder()~~ | Comparator | static | Not relevant. `sorted(reverse=True)` with no comparator already is reverse natural order. |
| x | comparing(f, keyComparator) | Comparator | static | Java's two-argument overload, comparing extracted keys with a `Comparator` rather than natural ordering. Previously decided against - the disambiguation problem and the sync/async asymmetry the decline cited (`openspec/changes/archive/2026-08-28-add-comparator-chaining/design.md`) turned out narrower than stated; re-decided alongside `then_comparing()`'s widened acceptance of a bare `Comparator` above. This is `comparing()`'s `key_comparator` parameter above, not a separate function. |
| x | thenComparing(f, keyComparator) | Comparator | instance | Java's two-argument `thenComparing` overload, for the same reasons as the `comparing(f, keyComparator)` row above. This is `then_comparing()`'s `key_comparator` parameter above, not a separate method. |
|   | ~~comparing_int(f)~~ / ~~comparing_long(f)~~ / ~~comparing_double(f)~~ | Comparator | static | Not relevant. These exist in Java so the extracted key is compared as a primitive rather than a boxed `Integer`/`Long`/`Double` - the same autoboxing problem `map_to_int()` and its siblings solve on the `Stream` table, and the same answer: Python numbers are already objects with no boxing cost, so `comparing()` over a numeric key is what these would be. |
|   | ~~then_comparing_int(f)~~ / ~~then_comparing_long(f)~~ / ~~then_comparing_double(f)~~ | Comparator | instance | Not relevant, same reasoning as the row above. `then_comparing()` over a numeric key extractor already is this. |
|   | ~~compare(a, b)~~ | int | instance | Not relevant. In Java this is the single abstract method that makes `Comparator` a functional interface. Here a `Comparator` **is** a callable of two arguments returning a 3-way `int` (`snakestream.type`), sync or async, so calling one is calling it - there is no named method to be at parity with. `KeyComparator` is callable in exactly that way, which is why it is accepted anywhere a hand-written comparator is. |
|   | ~~equals(obj)~~ | bool | instance | Not relevant. Java redeclares `Object.equals` on `Comparator` only to document that two comparators imposing the same ordering may be considered equal; it imposes no behaviour. Python's `==` needs no such redeclaration. |

## Migration

Every breaking change is recorded in [CHANGELOG.md](CHANGELOG.md), newest first,
with what changed, whether the break is loud or silent, and what to do about it.
Until release 1.0.0, expect that list to grow.
