# Snakestream
*Streams like in java, but for snakes*

Most programmers just want to see the code, so let's skip directly to a usage example:

```python
import asyncio
from snakestream import Stream
from snakestream.collector import to_generator

int_2_letter = {
    1: 'a',
    2: 'b',
    3: 'c',
    4: 'd',
    5: 'e',
}


async def async_int_to_letter(x: int) -> str:
    await asyncio.sleep(0.01)
    return int_2_letter[x]


async def main():
    it = Stream.of([1, 3, 4, 5, 6]) \
        .filter(lambda n: 3 < n < 6) \
        .map(async_int_to_letter) \
        .collect(to_generator)

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
- Switch between parallel and sequential mode
- [Autoclose](#auto-close) streams with `contextlib`
- Generate indefinite streams [simpler than in Java](#the-generate-function)

### Auto Close

Contextlib already supports something that is very similar to the AutoClose from Java. Just as long as your class has the .close() attribute it will be called. In this case it's very fortunate that the Java API and contextlib play so nice together. Here is an example:

```python
from contextlib import closing

with closing(Stream.of([1, 2, 3, 4, 1, 2, 3, 4])) as stream:
    it = await stream \
        .map(lambda x: int_2_letter[x]) \
        .distinct() \
        .collect(to_list)
```

This can be especially useful if you are subclassing Stream to do something that is kinda like IO related and you have some resource that needs to get relased after the stream. You would then just add the logic to do that in your .close() method and contextlib will handle the rest

### The generate() function

In snakestream this has been omitted since python has generators and those can be sent in as a source with `Stream.of()`

## API
### BaseStream

| function       | returns  | type     | summary                                                                                             |
| -------------- | -------- | ---------| --------------------------------------------------------------------------------------------------- |
| is_parallel()  | bool     | instance | Returns whether this stream, if a terminal operation were to be executed, would execute in parallel |

### Stream

| done | function                        | returns                     | type     | summary                                                                                 |
| ---- | ------------------------------- | --------------------------- | ---------|---------------------------------------------------------------------------------------- |
| x | all_match(predicate: Predicate) | bool                        | instance | Returns whether all elements of this stream match the provided predicate                |
| x | any_match(predicate: Predicate) | bool                        | instance | Returns whether any elements of this stream match the provided predicate                |
| x | builder()                       | StreamBuilder               | static   | Returns a builder for a Stream                                                          |
| x | collect(collector: Callable)    | Union[List, AsyncGenerator] | instance | Performs a mutable reduction operation on the elements of this stream using a Collector |
| x | concat(a: Stream, b: Stream)    | Stream                      | static   | Creates a lazily concatenated stream whose elements are all the elements of the first stream followed by all the elements of the second stream |
| x | count()                         | int                         | instance | Returns the count of elements in this stream                                            |
| x | distinct()                      | Stream                      | instance | Returns a stream consisting of the distinct elements (using ==) of this stream          |
| x | empty()                         | Stream                      | static   | Returns an empty sequential Stream                                                      |
| x | filter(predicate: Predicate)    | Stream                      | instance | Returns a stream consisting of the elements of this stream that match the given predicate |
| x | find_any()                      | Optional[T]               | instance | Returns an Optional describing some element of the stream, or an empty Optional if the stream is empty |
|   | _find_first()_                | Optional[T]             | instance | Not implemented yet, depends on the implementaton of `ordered()` |
| x | flat_map(flat_mapper: FlatMapper) | Stream                    | instance | Returns a stream consisting of the results of replacing each element of this stream with the contents of a mapped stream produced by applying the provided mapping function to each element |
|   | _flat_map_to_double(flat_mapper: FlatMapper)_ | Stream    | instance | Not implemented yet | 
|   | _flat_map_to_int(flat_mapper: FlatMapper)_ | Stream       | instance | Not implemented yet | 
|   | ~~flat_map_to_long(flat_mapper: FlatMapper)~~ | Stream      | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. | 
| x | for_each(consumer: Callable[T]) | Any                         | instance | Performs an action for each element of this stream | 
|   | _for_each_ordered(consumer: Callable[T])_ | Any           | instance | Not implemented yet, depends on the implementaton of `ordered()` | 
|   | ~~generate(supplier: Callable[T])~~           | Stream        | static   | Not relevant. We can send in generators directly to `Stream.of()` already|
| x | iterate(seed: T, nxt: Callable[[T], T]) | Stream | static | Returns an infinite sequential ordered Stream produced by iterative application of a function f to an initial element seed, producing a Stream consisting of seed, f(seed), f(f(seed)), etc. |
| x | limit(max_size: int)                    | Stream | instance | Returns a stream consisting of the elements of this stream, truncated to be no longer than max_size() in length. |
| x | map(mapper: Mapper)                     | Stream | instance | Returns a stream consisting of the results of applying the given function to the elements of this stream. |
|   | _map_to_double(mapper: ToDoubleMapper)_  | Stream | instance | Returns a DoubleStream consisting of the results of applying the given function to the elements of this stream. |
|   | _map_to_int(mapper: ToIntMapper)_       | Stream | instance | Returns an IntStream consisting of the results of applying the given function to the elements of this stream. |
|   | ~~map_to_long(mapper: ToLongMapper)~~   | Stream | instance | Not relevant. The interpreter automatically handles larger than 32bit numbers. |
| x | max(comparator: Comparator)             | Optional[T] | instance | Returns the maximum element of this stream according to the provided Comparator. |
| x | min(comparator: Comparator)             | Optional[T] | instance | Returns the minimum element of this stream according to the provided Comparator. |
| x | none_match(predicate: Predicate)        | bool | instance | Returns whether no elements of this stream match the provided predicate. |
| x | of(*args, *kwargs)                      | Stream | static | Returns a sequential ordered stream whose elements are the specified values |
| x | peek(self, consumer: Consumer)          | Stream | instance | Returns a stream consisting of the elements of this stream, additionally performing the provided action on each element as elements are consumed from the resulting stream. |

## Migration
These are a list of the known breaking changes. Until release 1.0.0 focus will be on implementing features and changing things that does not align with how streams work in java.
- **0.2.4 -> 0.3.0:** `stream_of()` has been removed in favour of `Stream.of()` for getting closer to the java api.
- **0.1.0 -> 0.2.0:** The `unique()` function has been renamed `distinct()`. So rename all imports of that function, and it should be OK
- **0.0.5 -> 0.0.6:** The `stream()` function has been renamed `stream_of()`. So rename all imports of that function, and it should be OK

## Left to do:

BaseStream:
- iterator()
- spliterator()
- unordered()

Stream:
- collect(Supplier<R> supplier, BiConsumer<R,? super T> accumulator, BiConsumer<R,R> combiner)
- flatMapToDouble(Function<? super T,? extends DoubleStream> mapper)
- flatMapToInt(Function<? super T,? extends IntStream> mapper)
- flatMapToLong(Function<? super T,? extends LongStream> mapper)
- forEachOrdered(Consumer<? super T> action)
- iterate(T seed, UnaryOperator<T> f)
- limit(long maxSize)
- mapToDouble(ToDoubleFunction<? super T> mapper)
- mapToInt(ToIntFunction<? super T> mapper)
- mapToLong(ToLongFunction<? super T> mapper)

- reduce(BinaryOperator<T> accumulator) // have done the one with the identity
- skip(long n)
- sorted() // have done the one with a comparator
- toArray()
- toArray(IntFunction<A[]> generator)
