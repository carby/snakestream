# Snakestream
*Streams like in java, but for snakes*

Most programmers just want to see the code, so let's skip directly to a usage example:

```python
import asyncio
from snakestream import Stream
from snakestream.collector import to_generator

int_2_letter = {
    1: "a",
    2: "b",
    3: "c",
    4: "d",
    5: "e",
}


async def async_int_to_letter(x: int) -> str:
    await asyncio.sleep(0.01)
    return int_2_letter[x]


async def main():
    it = Stream.of([1, 3, 4, 5, 6]).filter(lambda n: 3 < n < 6).map(async_int_to_letter).collect(to_generator)

    async for x in it:
        print(x)


asyncio.run(main())
```
Notice how the stream returns a generator. We could also have awaited the stream and collected to a list just to give an idea of what could be done.

When we run this code the output becomes:

```bash
~/t/test> python test.py
d
e
```

## What is Snakestream?

This is a python streaming api that tries to bring a similar feature set that came into Java 8 with it's streaming api.

One situation where you can use it is to break apart those nested list comprehensions. Using a fluent interface syntax can bring better clarity in such complex cases and absolutely more resilitent to introduction new steps in the stream.

Once we reach some sort of feature parity with Java 8 then maybe we move on to implement the improvements in Java 9. However there will not be a complete feature parity because the languages are different. Prime example is that we dont really speak about arrays in python but, there we use lists or sets. Another example in java streams a major point are the functional interfaces, however python is a functional language, that means that Suppliers and Consumers and all of that stuff can be simply implemented in python with just regular functional programming. So that's the road map as of now, we will get as close as we can with a reasonable effort put into it.

## Features

> [!NOTE]
> This library is under development and has not reached version 1.0 yet. Backwards compatability can still be broken.

- Create a stream from a List, Generator, AsyncGenerator, Itertor, AsyncIterator or just an object
- Process your stream with both synchronous or asynchronous functions.
- Switch between parallel and sequential mode ([not true CPU parallelism yet](#about-parallel))
- [Autoclose](#auto-close) streams with `contextlib`
- Generate indefinite streams [simpler than in Java](#the-generate-function)

### About `.parallel()`

Unlike Java's `parallelStream()`, snakestream's `.parallel()` does not run on separate OS threads or processes. It races `asyncio` tasks over a shared generator, which speeds up I/O-bound work (e.g. a mapper that awaits a network call) but is still GIL-bound and offers no real speedup for CPU-bound work.

We know `.concurrent()`/`CONCURRENCY` would be the more idiomatic name for what this actually does, but we're deliberately keeping the `.parallel()`/`PROCESSES` naming so that if real (multiprocess) parallelism is implemented later, it doesn't require a second breaking rename.

Real parallelism is blocked on a genuine technical problem, not just unscoped effort: a process-pool-backed implementation would need to serialize every mapper/predicate/comparator/accumulator/combiner across the process boundary, and stdlib `pickle` can't serialize lambdas or local closures — the idiomatic way to call every operation in this library. It also can't pickle generators or async generators at all, so the stream's source can never be shipped to a worker whole. And even fully picklable, purely synchronous callables don't finish the job, since an async user callable would require each worker process to bootstrap its own event loop rather than just calling a function. Until there's both a concrete use case for true parallelism and an answer to that serialization problem, `.parallel()` will keep meaning "concurrent," not "parallel." See `roadmap.md`'s **Later** section for details.

### Auto Close

Contextlib already supports something that is very similar to the AutoClose from Java. Just as long as your class has the .close() attribute it will be called. In this case it's very fortunate that the Java API and contextlib play so nice together. Here is an example:

```python
from contextlib import closing

with closing(Stream.of([1, 2, 3, 4, 1, 2, 3, 4])) as stream:
    it = await stream.map(lambda x: int_2_letter[x]).distinct().collect(to_list)
```

This can be especially useful if you are subclassing Stream to do something that is kinda like IO related and you have some resource that needs to get relased after the stream. You would then just add the logic to do that in your .close() method and contextlib will handle the rest

### The generate() function

In snakestream this has been omitted since python has generators and those can be sent in as a source with `Stream.of()`

## API
### BaseStream

| function       | returns  | type     | summary                                                                                             |
| -------------- | -------- | ---------| --------------------------------------------------------------------------------------------------- |
| is_ordered()   | bool     | instance | Returns whether this stream is still considered order-dependent (i.e. `unordered()` has not been called) |
| is_parallel()  | bool     | instance | Returns whether this stream, if a terminal operation were to be executed, would execute in parallel |
| iterator()     | AsyncGenerator | instance | Composes the current chain and returns the resulting async generator directly, without consuming it, so the caller can drive iteration themselves |
| parallel()     | Stream   | instance | Composes the current chain and returns an equivalent stream that will execute in parallel           |
| sequential()   | Stream   | instance | Composes the current chain and returns an equivalent stream that will execute sequentially          |
| unordered()    | Stream   | instance | Marks the stream as not order-dependent; the flag persists across `parallel()`/`sequential()` mode switches |

### Stream

| done | function                        | returns                     | type     | summary                                                                                 |
| ---- | ------------------------------- | --------------------------- | ---------|---------------------------------------------------------------------------------------- |
| x | all_match(predicate: Predicate) | bool                        | instance | Returns whether all elements of this stream match the provided predicate                |
| x | any_match(predicate: Predicate) | bool                        | instance | Returns whether any elements of this stream match the provided predicate                |
| x | builder()                       | StreamBuilder               | static   | Returns a builder for a Stream                                                          |
| x | collect(collector: Callable)    | Union[List, AsyncGenerator] | instance | Performs a mutable reduction operation on the elements of this stream using a Collector |
| x | collect(supplier: Supplier, accumulator: BiConsumer, combiner: BiConsumer) | R | instance | Performs a mutable reduction on the elements of this stream: `supplier` creates the result container, `accumulator` folds each element into it. `combiner` is accepted for signature parity but not invoked - snakestream's `collect()` always folds over one composed stream, sequential or parallel, with no independent partitions to merge. |
| x | concat(a: Stream, b: Stream)    | Stream                      | static   | Creates a lazily concatenated stream whose elements are all the elements of the first stream followed by all the elements of the second stream |
| x | count()                         | int                         | instance | Returns the count of elements in this stream                                            |
| x | distinct()                      | Stream                      | instance | Returns a stream consisting of the distinct elements (using ==) of this stream          |
| x | empty()                         | Stream                      | static   | Returns an empty sequential Stream                                                      |
| x | filter(predicate: Predicate)    | Stream                      | instance | Returns a stream consisting of the elements of this stream that match the given predicate |
| x | find_any()                      | Optional[T]               | instance | Returns an Optional describing some element of the stream, or an empty Optional if the stream is empty |
| x | find_first()                    | Optional[T]                | instance | Returns an Optional describing the first element of the stream in encounter order, or an empty Optional if the stream is empty. On `ParallelStream`, preserves encounter order when the stream is ordered (the default); races like `find_any()` when `.unordered()` has been called |
| x | flat_map(flat_mapper: FlatMapper) | Stream                    | instance | Returns a stream consisting of the results of replacing each element of this stream with the contents of a mapped stream produced by applying the provided mapping function to each element |
|   | ~~flat_map_to_double(flat_mapper: FlatMapper)~~ | Stream    | instance | Not relevant. Exists in Java to avoid autoboxing `double`s and to expose numeric-only ops (`sum()`, `average()`) that a generic `Stream<T>` can't offer. Python numbers are already objects with no boxing cost, and `sum()`/`min()`/`max()` work on any iterable, so there's no equivalent problem to solve. | 
|   | ~~flat_map_to_int(flat_mapper: FlatMapper)~~ | Stream       | instance | Not relevant, same reasoning as `flat_map_to_double`. | 
|   | ~~flat_map_to_long(flat_mapper: FlatMapper)~~ | Stream      | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. | 
| x | for_each(consumer: Callable[T]) | Any                         | instance | Performs an action for each element of this stream | 
| x | for_each_ordered(consumer: Callable[T]) | Any               | instance | Performs an action for each element of this stream, in the encounter order of the stream if the stream has a defined encounter order | 
|   | ~~generate(supplier: Callable[T])~~           | Stream        | static   | Not relevant. We can send in generators directly to `Stream.of()` already|
| x | iterate(seed: T, nxt: Callable[[T], T]) | Stream | static | Returns an infinite sequential ordered Stream produced by iterative application of a function f to an initial element seed, producing a Stream consisting of seed, f(seed), f(f(seed)), etc. |
| x | limit(max_size: int)                    | Stream | instance | Returns a stream consisting of the elements of this stream, truncated to be no longer than max_size() in length. |
| x | map(mapper: Mapper)                     | Stream | instance | Returns a stream consisting of the results of applying the given function to the elements of this stream. |
|   | ~~map_to_double(mapper: ToDoubleMapper)~~  | Stream | instance | Not relevant, same reasoning as `flat_map_to_double`. |
|   | ~~map_to_int(mapper: ToIntMapper)~~       | Stream | instance | Not relevant, same reasoning as `flat_map_to_double`. |
|   | ~~map_to_long(mapper: ToLongMapper)~~   | Stream | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. |
| x | max(comparator: Comparator)             | Optional[T] | instance | Returns the maximum element of this stream according to the provided Comparator. |
| x | min(comparator: Comparator)             | Optional[T] | instance | Returns the minimum element of this stream according to the provided Comparator. |
| x | none_match(predicate: Predicate)        | bool | instance | Returns whether no elements of this stream match the provided predicate. |
| x | of(*args: T)                            | Stream | static | Returns a sequential ordered stream whose elements are the specified values |
| x | peek(self, consumer: Consumer)          | Stream | instance | Returns a stream consisting of the elements of this stream, additionally performing the provided action on each element as elements are consumed from the resulting stream. |
| x | reduce(identity: T \| R, accumulator: Accumulator) | T \| R | instance | Performs a reduction on the elements of this stream, using the provided identity value and an associative accumulation function, and returns the reduced value. |
| x | reduce(accumulator: BinaryOperator) | T \| None | instance | Performs a reduction on the elements of this stream, using an associative accumulation function seeded by the stream's own first element, and returns the reduced value, or None if the stream is empty. |
| x | skip(n: int)                             | Stream | instance | Returns a stream consisting of the remaining elements of this stream after discarding the first n elements of the stream. |
| x | sorted(comparator: Comparator \| None = None, reverse: bool = False) | Stream | instance | Returns a stream consisting of the elements of this stream, sorted according to natural ordering, or according to the provided Comparator if given. |
| x | to_array()                              | List[T] | instance | Returns a list containing the elements of this stream. Equivalent to `collect(to_list)`; Java's `toArray()` returns an array, but Python has no distinct array type competing with `list`. |
|   | ~~toArray(generator: IntFunction[Array[T]])~~ | Array[T] | instance | Not relevant. Exists in Java to work around the lack of runtime generic-array construction, letting callers get a correctly-typed array instead of `Object[]`. Python's `list` has no array/generic-array distinction to work around, so there's no equivalent problem for this overload to solve. |

### Collectors

| done | function                                              | returns   | type    | summary                                                                 |
| ---- | ------------------------------------------------------ | --------- | ------- | ------------------------------------------------------------------------ |
| x | joining(delimiter: str = "", prefix: str = "", suffix: str = "") | Collector | factory | Returns a collector, for use with `collect()`, that concatenates the stream's `str` elements, separated by `delimiter` and wrapped in `prefix`/`suffix`. |
| x | counting() | Collector | factory | Returns a collector, for use with `collect()`, that counts the stream's elements as an `int`. |
| x | summing_int(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and sums the results as an `int`. |
| x | summing_long(mapper) | Collector | factory | Same as `summing_int`; kept as a separate name for parity with Java's `summingLong`, since Python has no `int`/`long` distinction. |
| x | summing_double(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and sums the results as a `float`. |
| x | averaging_int(mapper) | Collector | factory | Returns a collector that maps each element via `mapper` and returns the arithmetic mean as a `float` (`0.0` for an empty stream). |
| x | averaging_long(mapper) | Collector | factory | Same as `averaging_int`; kept as a separate name for parity with Java's `averagingLong`. |
| x | averaging_double(mapper) | Collector | factory | Same as `averaging_int`; kept as a separate name for parity with Java's `averagingDouble`. |
| x | min_by(comparator) | Collector | factory | Returns a collector, for use with `collect()`, that selects the smallest element per the 3-way-int `comparator`, `None` for an empty stream, first-of-tied-elements wins. Wraps `Stream.min()`'s existing logic. |
| x | max_by(comparator) | Collector | factory | Same as `min_by`, but selects the largest element. Wraps `Stream.max()`'s existing logic. |
| x | reducing(binary_operator) / reducing(identity, binary_operator) / reducing(identity, mapper, binary_operator) | Collector | factory | Returns a collector that folds the stream via `binary_operator`, matching Java's three `Collectors.reducing` overloads: no-identity (seeds from the first element, `None` for an empty stream), with `identity` (returns `identity` unchanged for an empty stream), and with `identity` + `mapper` (maps each element before folding). Mirrors `Stream.reduce()`'s existing semantics. |
| x | to_map(key_mapper, value_mapper, merge_function=None) | Collector | factory | Returns a collector, for use with `collect()`, that builds a `dict` from `key_mapper`/`value_mapper` applied to each element. Raises `ValueError` on a duplicate key unless `merge_function` is given, in which case the colliding values are resolved via `merge_function(existing, new)`. |
| x | to_set() | Collector | factory | Returns a collector, for use with `collect()`, that builds a `set` from the stream's elements. |
| x | grouping_by(classifier, downstream=to_list) | Collector | factory | Returns a collector, for use with `collect()`, that buckets elements by `classifier` into `dict[K, list[T]]`, or `dict[K, R]` if a `downstream` collector is given to reduce each group. Only keys `classifier` actually produced appear. |
| x | partitioning_by(predicate, downstream=to_list) | Collector | factory | Returns a collector, for use with `collect()`, that splits elements into `dict[True/False, list[T]]` per `predicate`, or `dict[True/False, R]` if a `downstream` collector is given. Both keys are always present, even if one partition is empty. |

## Migration
These are a list of the known breaking changes. Until release 1.0.0 focus will be on implementing features and changing things that does not align with how streams work in java.
- **0.3.5 -> next:** The sync/async dispatch contract for every user-supplied callable (predicate, mapper, comparator, consumer, accumulator) invoked once per element narrows from per-result to per-callable-per-composition: whether a callable's results are awaited is now decided once at that callable's first invocation in a composition and held for the rest of that composition, instead of being re-checked on every result. A callable that returns an awaitable for some elements and a plain value for others - previously handled correctly - is no longer supported; its behavior is undefined. This has no Java analogue, since Java's functional interfaces cannot vary their return type per invocation. See `openspec/changes/optimize-callable-dispatch`.
- **0.3.5 -> next:** `map()`, `filter()`, `flat_map()`, `sorted()`, `distinct()`, `peek()`, `limit()`, `skip()`, `sequential()`, and `parallel()` now return a **new** `Stream`/`ParallelStream` instance instead of mutating and returning `self`. Once a reference has been used to build a further instance this way (or has been terminally consumed), using that same old reference again for any of those ops, or for a terminal operation, raises a new `IllegalStateException` (`snakestream.exception`). This does not affect repeating a terminal operation on a reference that was never used to build a further instance (still supported, still returns an empty result on an exhausted source), nor `on_close()`/`close()`, which remain unaffected and continue to work on any reference regardless of this state. Callers relying on chaining off an intermediate result while continuing to build on the original reference must use the new reference returned by the op instead.
- **0.3.5 -> next:** `StreamBuilder.build()` now returns a `Stream` over a snapshot of the builder's elements instead of a reference to its live internal list. `add()`/`accept()` calls made after `build()` no longer leak into the already-built stream.
- **0.3.5 -> next:** `Stream.of()` no longer accepts keyword arguments. `Stream.of(a=1, b=2)` used to produce `[("a", 1), ("b", 2)]`; this had no Java equivalent and was undiscoverable from the signature. Callers must switch to `Stream.of(*some_dict.items())` for the equivalent stream of tuples.
- **0.3.5 -> next:** `Stream.of("some string")` and `Stream.of(b"some bytes")` (and constructing a `Stream` from a `str`/`bytes` source generally) now yield a single scalar element instead of spreading into individual characters/bytes, matching how Java's `Stream.of(T...)` treats `String`/`byte[]` arguments atomically. Callers relying on the old char/byte-spreading behavior must switch to e.g. `Stream.of(*"some string")`.
- **0.3.5 -> next:** `sorted()`/`min()`/`max()` now raise `TypeError` if the supplied comparator returns `bool` instead of `int`. Python's `bool` is a subclass of `int`, so a bool-returning comparator (e.g. `lambda x, y: x > y`) previously satisfied the `Comparator` type silently while violating its 3-way sign contract. Callers must switch to an int-returning comparator (e.g. `lambda x, y: x - y`).
- **0.3.5 -> next:** `min()`/`max()` now require a Java-style 3-way comparator (negative/zero/positive int, matching `sorted()`), not a bool. Callers passing a bool-returning comparator (e.g. `lambda x, y: x > y`) must switch to one returning an int (e.g. `lambda x, y: x - y`) or their result will silently be wrong. This also fixes `min()`'s previous last-wins tie-break so it now keeps the first of equal elements, matching `max()`.
- **0.2.4 -> 0.3.0:** `stream_of()` has been removed in favour of `Stream.of()` for getting closer to the java api.
- **0.1.0 -> 0.2.0:** The `unique()` function has been renamed `distinct()`. So rename all imports of that function, and it should be OK
- **0.0.5 -> 0.0.6:** The `stream()` function has been renamed `stream_of()`. So rename all imports of that function, and it should be OK
