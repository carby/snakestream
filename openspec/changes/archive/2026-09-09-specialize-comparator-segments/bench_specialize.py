"""Roadmap A: plan-of-closures vs baseline vs the shared-tail shape.

  baseline - verbatim copy of src/snakestream/comparator.py
  shared   - baseline + _compare_keys(ea, eb, comparator)  (the item's shape)
  plan     - each segment specialized into (extract, compare) closures at
             construction; the tail exists once, and the two per-segment
             coroutines (_segment_sign_async, _extract_pair_async) are gone
  null     - byte-identical copy of baseline (noise floor)

Same protocol as bench_b2: 2000 pairs per sample, order-balanced rotation,
comparators built once per shape, min and median over many rounds.
"""

import asyncio
import random
import statistics
import time

import comp_baseline
import comp_null
import comp_plan
import comp_shared

N = 2_000
IMPLS = (
    ("baseline", comp_baseline),
    ("shared", comp_shared),
    ("plan", comp_plan),
    ("null", comp_null),
)


def _make_pairs(n: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randint(0, 1_000_000), rng.randint(0, 1_000_000)) for _ in range(n)]


PAIRS = _make_pairs(N, seed=1)
# A tenth of the pairs carry a None side, so the tolerant shapes exercise the
# null branch as well as the tail rather than only the tail.
PAIRS_NULLY = [(None if i % 10 == 0 else a, b) for i, (a, b) in enumerate(PAIRS)]


async def _canonical(x: int) -> int:
    await asyncio.sleep(0)
    return x


async def _cheap(x: int) -> int:
    return x


def _int_cmp(a: int, b: int) -> int:
    return (a > b) - (a < b)


def _bench_sync(comparator, pairs) -> float:
    start = time.perf_counter()
    for a, b in pairs:
        comparator(a, b)
    return (time.perf_counter() - start) / N * 1e9


async def _bench_async(comparator, pairs) -> float:
    start = time.perf_counter()
    for a, b in pairs:
        await comparator(a, b)
    return (time.perf_counter() - start) / N * 1e9


async def _run(label: str, build, is_async: bool, rounds: int, pairs=PAIRS) -> None:
    built = {name: build(mod) for name, mod in IMPLS}
    samples: dict[str, list[float]] = {name: [] for name, _ in IMPLS}
    for r in range(rounds):
        order = IMPLS[r % len(IMPLS) :] + IMPLS[: r % len(IMPLS)]
        for name, _mod in order:
            c = built[name]
            samples[name].append(await _bench_async(c, pairs) if is_async else _bench_sync(c, pairs))

    base_lo = min(samples["baseline"])
    base_med = statistics.median(samples["baseline"])
    print(f"\n{label}  (rounds={rounds})")
    print(f"  baseline: {base_lo:.1f} ns/cmp (min), {base_med:.1f} (median)")
    print(f"  {'impl':<9} {'min ns':>9} {'d(min) ns':>10} {'d(min) %':>9} {'d(med) %':>9}")
    for name, _ in IMPLS:
        if name == "baseline":
            continue
        lo, med = min(samples[name]), statistics.median(samples[name])
        print(
            f"  {name:<9} {lo:>9.1f} {lo - base_lo:>+10.1f} "
            f"{(lo - base_lo) / base_lo * 100:>+8.2f}% {(med - base_med) / base_med * 100:>+8.2f}%"
        )


async def main() -> None:
    print(f"N={N} pairs, comparators built once per shape, order-balanced rotation.")

    await _run("sync, one key segment (min/max's shape)", lambda m: m.comparing(lambda x: x), False, 1000)
    await _run("sync, comparator segment", lambda m: m.comparing(lambda x: x, _int_cmp), False, 1000)
    await _run("sync, two-segment chain", lambda m: m.comparing(lambda x: x).then_comparing(lambda x: -x), False, 1000)
    await _run(
        "sync tolerant, 10% None elements",
        lambda m: m.nulls_first(m.comparing(lambda x: x)),
        False,
        1000,
        PAIRS_NULLY,
    )
    await _run("async CHEAP, one key segment", lambda m: m.comparing(_cheap), True, 600)
    await _run("async CHEAP tolerant, 10% None", lambda m: m.nulls_first(m.comparing(_cheap)), True, 600, PAIRS_NULLY)
    await _run(
        "async CHEAP, mixed chain (async seg + sync seg)",
        lambda m: m.comparing(_cheap).then_comparing(lambda x: -x),
        True,
        600,
    )
    await _run("async CANON, one key segment", lambda m: m.comparing(_canonical), True, 300)
    await _run("async CANON tolerant, 10% None", lambda m: m.nulls_first(m.comparing(_canonical)), True, 300, PAIRS_NULLY)


if __name__ == "__main__":
    asyncio.run(main())
