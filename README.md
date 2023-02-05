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
    - unique()
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
    it = stream_of([1, 3, 4, 5, 6]) \
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

### Migration
These are a list of the known breaking changes. Until release 1.0.0 focus will be on implementing features and changing things that does not align with how streams work in java.
- **0.0.5 -> 0.0.6:** The `stream()` function has been renamed `stream_of()`. So rename all imports of that function, and it should be OK
