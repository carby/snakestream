"""Benchmark harness for merge-segment-sign-on-natural-ordering.

20,000 elements, interleaved round-robin across shapes, best of 3, median of
25 rounds, ns/element. Kept alongside baseline.txt and post_change.txt in the
change directory, rather than deleted, so the roadmap's closing entry can
reproduce the figures it cites.

Usage: uv run python openspec/changes/merge-segment-sign-on-natural-ordering/bench_segment_sign.py
"""

import asyncio
import random
import statistics
import time

from snakestream.comparator import KeyComparator, comparing

N = 20_000
ROUNDS = 25
REPEATS = 3


def _make_pairs(n: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randint(0, 1_000_000), rng.randint(0, 1_000_000)) for _ in range(n)]


PAIRS = _make_pairs(N, seed=1)


def _int_comparator(a: int, b: int) -> int:
    return (a > b) - (a < b)


def _bench_sync(comparator: KeyComparator) -> float:
    best = None
    for _ in range(REPEATS):
        start = time.perf_counter()
        for a, b in PAIRS:
            comparator(a, b)
        elapsed = time.perf_counter() - start
        if best is None or elapsed < best:
            best = elapsed
    assert best is not None
    return best / N * 1e9


async def _identity_async(x: int) -> int:
    await asyncio.sleep(0)
    return x


async def _bench_async(comparator: KeyComparator) -> float:
    best = None
    for _ in range(REPEATS):
        start = time.perf_counter()
        for a, b in PAIRS:
            await comparator(a, b)
        elapsed = time.perf_counter() - start
        if best is None or elapsed < best:
            best = elapsed
    assert best is not None
    return best / N * 1e9


def _key_segment() -> KeyComparator:
    return comparing(lambda x: x)


def _comparator_segment() -> KeyComparator:
    return comparing(lambda x: x, _int_comparator)


def _two_segment_chain() -> KeyComparator:
    return comparing(lambda x: x).then_comparing(lambda x: -x)


def _async_key_segment() -> KeyComparator:
    return comparing(_identity_async)


async def main() -> None:
    # Interleaved round-robin: build+measure each shape in turn, one round at
    # a time, rather than finishing one shape's 25 rounds before starting the
    # next -- so a drift in system load lands on every shape equally.
    shapes_sync = {
        "key segment": _key_segment,
        "comparator segment": _comparator_segment,
        "two-segment chain": _two_segment_chain,
    }
    results_sync: dict[str, list[float]] = {name: [] for name in shapes_sync}
    for _round in range(ROUNDS):
        for name, build in shapes_sync.items():
            results_sync[name].append(_bench_sync(build()))

    results_async: list[float] = [await _bench_async(_async_key_segment()) for _round in range(ROUNDS)]

    print("sync shapes (ns/element, median, min-max range):")
    for name, samples in results_sync.items():
        print(f"  {name}: {statistics.median(samples):.1f}  ({min(samples):.1f}-{max(samples):.1f})")

    print("async shapes (ns/element, median, min-max range):")
    med, lo, hi = statistics.median(results_async), min(results_async), max(results_async)
    print(f"  async extractor, one key segment: {med:.1f}  ({lo:.1f}-{hi:.1f})")


if __name__ == "__main__":
    asyncio.run(main())
