## Context

See `proposal.md` — Why. This change is the foundation for the two that follow
(`spliterator()` plus a forking executor, then live combiners), and by design it
carries none of their risk: it touches no file under `src/`.

The measurements that justify the sequence were taken before it was proposed,
on free-threaded CPython 3.14.5 at 4 workers, and are recorded here because the
later changes will be argued against them.

| Shape | Result |
|---|---|
| CPU-bound in threads, GIL build | **1.01x** — no parallelism, as the roadmap assumed |
| CPU-bound in threads, free-threaded | **2.6–3.0x** |
| Per-element `asyncio.to_thread` | ~48µs overhead per element; needs >100µs of work per element to break even |
| Contiguous chunks, one `to_thread` per chunk | **2.5–2.7x** from ~4.4µs/element; break-even ~1.4µs/element |
| Async user callables, one event loop per worker thread | **2.17x**, against 2.23x for the sync equivalent |
| Existing suite on the free-threaded build | 1000 passed, unmodified |

**The distinction that governs the whole plan**: per-element offload multiplies
its overhead by the element count, so a cheap callable pays it N times — that is
the shape that is catastrophically slower, up to 500x on a trivial mapper.
Chunked offload pays it once per *worker*, so the cost is bounded at O(workers)
regardless of stream length. Measured at the worst point on the curve
(~0.1µs/element) the chunked penalty is +1.5ms in absolute terms, on a pipeline
that took 0.3ms. That is a bad ratio and a negligible cost, and the distinction
between those two readings is the reason chunking is the shape and per-element
offload is excluded outright.

## Goals / Non-Goals

**Goals:**

- Prove, in CI and continuously, that the library is correct on a free-threaded
  interpreter — before anything depends on it being so.
- Write down the thread-safety properties that currently hold, so change 2
  starts from a baseline rather than an assumption.
- Restore the per-leg gating of `ty`, `pip-audit` and coverage now that there is
  more than one leg for them to be redundant across.

**Non-Goals:**

- Any parallelism work. No `spliterator()`, no forking executor, no change to
  `execution.py`. This change would be equally correct if the following two were
  never written.
- Making anything faster. The free-threaded leg is a *correctness* check; the
  library gains no speed from it, because nothing in `src/` yet runs on more
  than one thread.
- Declaring a free-threaded build *required*. It is supported and tested; the
  GIL build remains fully supported and is where `ty`, the audit and coverage
  run.

## Decisions

**1. A free-threaded build is a matrix leg on `code_check`, and only there.**

The 3.14 bump kept the matrices at one element specifically so this would be a
matrix edit. It is, for `code_check`.

`install_smoke_test` does **not** get the leg, and an earlier draft of this
design was wrong to say it should. The reasoning offered then was that wheel
tags differ between builds and that a dependency might ship no free-threaded
wheel. Both were checked and neither holds for this package: `uv build --wheel`
produces `snakestream-<version>-py3-none-any.whl`, pure Python with no C
extension, so one artifact serves both builds; and `project.dependencies` is
empty, so there is no third-party wheel whose availability could differ. The leg
would `pip install` a byte-identical file twice.

The residual argument — that it would confirm the installed distribution
*imports* on a free-threaded interpreter — is already covered by the
`code_check` leg, which imports the package throughout a 1000-test suite. A
second leg proving the same thing more weakly is the kind of exhaustiveness that
makes CI slower without making it stronger.

**2. Re-introduce the three `if:` conditionals, on the GIL leg.**

The 3.14 bump removed them because a single-leg matrix made them vacuous, and
that was right. Two legs makes them meaningful again, and the original rationale
is unchanged: `ty`, `pip-audit` and the coverage threshold do not vary by
interpreter build. This is not a revert — the conditionals return with a
different condition and a different justification, and the spec states the
reasoning so it is not re-litigated at the next matrix change.

*Coverage deserves a specific note*, because it was the one with a real risk.
An early measurement showed 94% on the free-threaded build against 99% on the
GIL build, which would have meant the gate could not run there. That was wrong:
the run had installed the package alongside the source tree and coverage was
measuring two copies. A clean free-threaded virtualenv reports **1512
statements, 2 missed, 99%** — identical to the GIL build, statement for
statement. Recorded because the false result is the kind that gets repeated.

**3. The library must pass both legs with no build-conditional code.**

Stated as a requirement rather than left as a hope. If passing both legs ever
requires a `sys._is_gil_enabled()` branch in `src/`, that is a defect: the
guiding principle holds that observable behaviour must not diverge, and
diverging on the interpreter *build* is the same category as diverging on the
version. It also pre-answers a question change 2 will face — what `.parallel()`
does on a GIL build — with the answer already chosen: the same thing, simply
without the CPU speedup.

*And that answer is cheaper than it sounds, which is worth recording before
change 2 is written.* The forking executor's benefit is not uniformly
GIL-dependent. Measured on the same I/O-bound probe (400 elements, 5ms latency,
4 workers), chunks that race internally give **51.8x on the GIL build** against
**59.5x free-threaded** — because `asyncio` concurrency never needed
free-threading. What a GIL build loses is only the CPU-bound thread parallelism
(2.6-3.0x), which is exactly the thing the GIL makes impossible in the first
place. So supporting GIL builds costs one code path and forfeits nothing that
was ever available on them; the forking executor subsumes racing on **both**
builds, which is what makes retiring racing safe irrespective of the reader's
interpreter.

*Dropping GIL support is also not expressible even if it were wanted.*
Checked: PEP 508 defines no environment marker for free-threading — the
available set is `implementation_name`, `implementation_version`, `os_name`,
`platform_machine`, `platform_python_implementation`, `platform_release`,
`platform_system`, `platform_version`, `python_full_version`, `python_version`,
`sys_platform`, and none of them expresses it. `Py_GIL_DISABLED` is a
`sysconfig` variable, not metadata. "Free-threaded only" could therefore be
enforced only by an import-time `raise`, which would turn a resolvable
constraint into an `ImportError` for everyone on a stock interpreter, since
python.org, Debian and Homebrew all ship 3.14 GIL-enabled by default.

**4. Record the audit in the spec, not only in this document.**

The three properties found — no module-level mutable state, immutable
`ClassVar`s only, per-composition dispatch state — are the reason the library
passes on a free-threaded build today. Left in an archived design document they
would be a historical observation; in the `free-threaded-support` spec they are
a requirement, and a change that introduces module-level mutable state has
something to violate. That is the difference between an audit and a guarantee.

**The finding this audit hands forward, and it is the important one:**
`execution.py` holds exactly two lock sites, both `asyncio.Lock`, guarding the
shared-source pull. They are correct today because a single event loop owns
every branch. A forking executor running one event loop per worker *thread*
makes them cross-thread, and an `asyncio.Lock` does not synchronise across
threads — it is not thread-safe and was never meant to be. Change 2 must
replace them, and this is written here so that it is a known obligation rather
than a bug found by a flaky test.

## Risks / Trade-offs

- **CI time roughly doubles for the test/lint job.** → Accepted, and bounded on
  two sides: decision 2 keeps `ty`, the audit and coverage running once, and
  decision 1 keeps `install_smoke_test` at one leg. The duplicated work is lint,
  format and the suite — the work that can actually differ between builds.

- **`astral-sh/setup-uv` may not provision `3.14t` under the identifier
  assumed.** → The interpreter itself is confirmed available and installable
  (`uv python install 3.14t` succeeded, and the suite was run under it), so the
  question is only the action's spelling of the version. Verified in the first
  CI run rather than assumed; if the spelling differs the fix is one string.

- **The free-threaded leg is flaky in a way the GIL leg is not.** → This is the
  outcome worth wanting, not a risk to suppress: a race that only fails
  sometimes is exactly what the leg exists to surface. What would be a real
  problem is treating such a failure as flakiness and retrying it, so the spec
  states that build-conditional code is not an acceptable remedy.

- **Nothing here is exercised concurrently, so the leg proves less than it
  appears to.** → True and worth stating plainly. Today the suite is
  single-threaded on both builds, so the leg mostly proves the *interpreter*
  runs the library, not that the library is race-free under load. Its value
  compounds in change 2, when there is genuinely concurrent code for it to
  catch. Adding it first is what makes that change's failures legible.

## Migration Plan

Single commit. Nothing under `src/` changes, so there is no runtime rollback
concern; reverting removes a CI leg and two spec files.

Validation is the CI run itself. Locally, the evidence is a clean free-threaded
virtualenv (`uv venv --python 3.14t`, `uv pip install -e .` plus dev
dependencies) running the suite and the coverage gate, which reproduces both
legs on one machine.
