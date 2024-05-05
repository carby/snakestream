# Snakestream
**Java like streams for snakes**

This is a python streaming api with witch you can get a similar experience as with the Java streams api from Java 8. There is no feature parity, what has been done so far is a beginning, and we will see where the road takes us.

### Features
- Create a stream from a List, Generator or AsyncGenerator.
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

### Observe
This library is currently under heavy development and there will be breakage in the current phase. When version 1.0.0 is realeased, only then will backwards compatability be the top priority. Please refer to [Migration](#migration).


### Usage
A simple int stream with `.map()` and `.filter()`
```python
import asyncio
from snakestream import stream_of
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
Then in the shell
```shell
~/t/test> python test.py
d
e
```

### Auto Close
Contextlib already supports something that is very similar to the AutoClose from Java. Just as long as your class has the .close() attribute it will be called. In this case it's very fortunate that the Java API and contextlib play so nice together. Here is an example:

```
from contextlib import closing

with closing(Stream.of([1, 2, 3, 4, 1, 2, 3, 4])) as stream:
    it = await stream \
        .map(lambda x: int_2_letter[x]) \
        .distinct() \
        .collect(to_list)
```

This can be especially useful if you are subclassing Stream to do something that is kinda like IO related and you have some resource that needs to get relased after the stream. You would then just add the logic to do that in your .close() method and contextlib will handle the rest

### Migration
These are a list of the known breaking changes. Until release 1.0.0 focus will be on implementing features and changing things that does not align with how streams work in java.
- **0.2.4 -> 0.3.0:** stream_of() has been removed in favour of Stream.of() for getting closer to the java api.
- **0.1.0 -> 0.2.0:** The `unique()` function has been renamed `distinct()`. So rename all imports of that function, and it should be OK
- **0.0.5 -> 0.0.6:** The `stream()` function has been renamed `stream_of()`. So rename all imports of that function, and it should be OK

### Left to do:

BaseStream:
isParallel()
iterator()
spliterator()
unordered()

Stream:
collect(Supplier<R> supplier, BiConsumer<R,? super T> accumulator, BiConsumer<R,R> combiner)
flatMapToDouble(Function<? super T,? extends DoubleStream> mapper)
flatMapToInt(Function<? super T,? extends IntStream> mapper)
flatMapToLong(Function<? super T,? extends LongStream> mapper)
forEachOrdered(Consumer<? super T> action)
generate(Supplier<T> s)
iterate(T seed, UnaryOperator<T> f)
limit(long maxSize)
mapToDouble(ToDoubleFunction<? super T> mapper)
mapToInt(ToIntFunction<? super T> mapper)
mapToLong(ToLongFunction<? super T> mapper)

reduce(BinaryOperator<T> accumulator) // have done the one with the identity
skip(long n)
sorted() // have done the one with a comparator
toArray()
toArray(IntFunction<A[]> generator)
