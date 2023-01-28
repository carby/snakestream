# Snakestream
**Java streams for snakes**

This is a python streaming api with witch you can get a similar experience as with the Java streams api from Java 8. There is no feature parity, what has been done so far is a beginning, and we will see where the road takes us.

### Features
- Create a stream from a List, Generator or AsyncGenerator.
- Process your stream with both synchronous or asynchronous functions.
	- map()
	- filter()
	- flatMap()
- Terminal functions include:
	- collect()
	- reduce()

### Usage

```python
import asyncio
from snakestream import stream
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
    it = stream([1, 3, 4, 5, 6])
        .filter(lambda n: 3 < n < 6)
        .map(async_int_to_letter)
        .collect(to_generator)

    async for x in it:
        print(x)


asyncio.run(main())

```

```commandline
~/t/test> python test.py
d
e
```
