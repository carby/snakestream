"""Roadmap B, second pass: is the shared-tail cost a constant ns, or a constant %?

Run 1 showed +2.9%/+3.4% on a cheap async extractor and -0.7%/-0.4% on the
canonical one. If the extra call costs a fixed number of nanoseconds, both are
the same finding at different denominators. This pass reports absolute deltas
with more rounds, and carries the null test (baseline vs byte-identical copy)
through every shape as the floor.
"""

import asyncio
import random
import statistics
import time

import comp_baseline
import comp_null
import comp_shared

N = 2_000
IMPLS = (("baseline", comp_baseline), ("shared", comp_shared), ("null", comp_null))


def _make_pairs(n: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randint(0, 1_000_000), rng.randint(0, 1_000_000)) for _ in range(n)]


PAIRS = _make_pairs(N, seed=1)


async def _canonical(x: int) -> int:
    await asyncio.sleep(0)
    return x


async def _cheap(x: int) -> int:
    return x


def _build(mod, extractor, tolerant: bool):
    c = mod.comparing(extractor)
    return mod.nulls_first(c) if tolerant else c


def _bench_sync(comparator) -> float:
    start = time.perf_counter()
    for a, b in PAIRS:
        comparator(a, b)
    return (time.perf_counter() - start) / N * 1e9


async def _bench_async(comparator) -> float:
    start = time.perf_counter()
    for a, b in PAIRS:
        await comparator(a, b)
    return (time.perf_counter() - start) / N * 1e9


async def _run(label: str, extractor, tolerant: bool, is_async: bool, rounds: int) -> None:
    samples: dict[str, list[float]] = {name: [] for name, _ in IMPLS}
    built = {name: _build(mod, extractor, tolerant) for name, mod in IMPLS}
    for r in range(rounds):
        order = IMPLS[r % len(IMPLS) :] + IMPLS[: r % len(IMPLS)]
        for name, _mod in order:
            c = built[name]
            samples[name].append(await _bench_async(c) if is_async else _bench_sync(c))

    base_lo = min(samples["baseline"])
    base_med = statistics.median(samples["baseline"])
    print(f"\n{label}  (rounds={rounds})")
    print(f"  baseline: {base_lo:.1f} ns/cmp (min), {base_med:.1f} (median)")
    print(f"  {'impl':<8} {'d(min) ns':>10} {'d(med) ns':>10} {'d(min) %':>9} {'d(med) %':>9}")
    for name, _ in IMPLS:
        if name == "baseline":
            continue
        lo, med = min(samples[name]), statistics.median(samples[name])
        print(
            f"  {name:<8} {lo - base_lo:>+10.1f} {med - base_med:>+10.1f} "
            f"{(lo - base_lo) / base_lo * 100:>+8.2f}% {(med - base_med) / base_med * 100:>+8.2f}%"
        )


async def main() -> None:
    print(f"N={N} pairs. Comparators built once per shape. No None elements (every comparison reaches the tail).")
    await _run("async tolerant, CHEAP  (bare async def)", _cheap, True, True, 600)
    await _run("async tolerant, CANON  (await asyncio.sleep(0))", _canonical, True, True, 300)
    await _run("async intolerant, CHEAP", _cheap, False, True, 600)
    await _run("async intolerant, CANON", _canonical, False, True, 300)
    await _run("sync tolerant", lambda x: x, True, False, 1000)
    await _run("sync intolerant", lambda x: x, False, False, 1000)


if __name__ == "__main__":
    asyncio.run(main())
