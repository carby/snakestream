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

- Create a stream from a List, Generator, AsyncGenerator, Itertor, AsyncIterator or just an object
- Process your stream with both synchronous or asynchronous functions.
	- map()
	- filter()
	- flat_map()
    - sorted()
    - distinct()
    - peek()
- Terminal functions include:
	- collect()
	- reduce()
    - for_each()
    - max()
    - min()
    - find_fist()
    - all_match()

### Observe!

This library is currently under development and there will be breakage in the current phase. When version 1.0.0 is realeased, only then will backwards compatability be the top priority. Please refer to [Migration](#migration).

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

## Migration
These are a list of the known breaking changes. Until release 1.0.0 focus will be on implementing features and changing things that does not align with how streams work in java.
- **0.2.4 -> 0.3.0:** `stream_of()` has been removed in favour of `Stream.of()` for getting closer to the java api.
- **0.1.0 -> 0.2.0:** The `unique()` function has been renamed `distinct()`. So rename all imports of that function, and it should be OK
- **0.0.5 -> 0.0.6:** The `stream()` function has been renamed `stream_of()`. So rename all imports of that function, and it should be OK

## Left to do:

BaseStream:
- isParallel()
- iterator()
- spliterator()
- unordered()

Stream:
- collect(Supplier<R> supplier, BiConsumer<R,? super T> accumulator, BiConsumer<R,R> combiner)
- flatMapToDouble(Function<? super T,? extends DoubleStream> mapper)
- flatMapToInt(Function<? super T,? extends IntStream> mapper)
- flatMapToLong(Function<? super T,? extends LongStream> mapper)
- forEachOrdered(Consumer<? super T> action)
- generate(Supplier<T> s)
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
