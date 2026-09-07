# Parallel Worker Utilisation Specification

## Purpose

Defines how a parallel stream's source is distributed across workers: that a
source with more elements than there are workers reaches more than one of
them, that this holds from the very first elements rather than only once the
batch-size ramp has climbed, and that what is promised is distribution rather
than wall-clock speedup — the latter depends on the interpreter build and is
reported with its measurement rather than guaranteed. It exists because the
opposite used to be true: most of a small source's elements were drained into
a single worker's second batch, which made `.parallel()` slower than
`.sequential()` on it and forced callers to reason about batch counts before
choosing an execution mode.

## Requirements

### Requirement: A source larger than the worker count reaches more than one worker

A parallel stream whose source yields more elements than `WORKERS` SHALL
dispatch those elements across more than one worker, rather than draining the
whole source into a single worker's batch.

This is a property of how the executor batches a source, not of the work each
element carries: it SHALL hold for a cheap callable and an expensive one
alike, and SHALL hold on both the GIL-enabled and the free-threaded
interpreter build, since it concerns which worker receives an element rather
than whether workers execute concurrently.

#### Scenario: A source of 200 elements is not confined to one worker
- **WHEN** a stream over a 200-element source queues a mapping operation, is
  run under `.parallel()` with the default `WORKERS`, and is collected
- **THEN** more than one distinct worker thread SHALL have run a batch of that
  pipeline
- **AND** the collected result SHALL equal the result of the same pipeline run
  under `.sequential()`

#### Scenario: A source no larger than the worker count carries no such promise
- **WHEN** a stream over a source of `WORKERS` elements or fewer is run under
  `.parallel()` and collected
- **THEN** the collected result SHALL still equal the sequential result
- **AND** the number of workers that ran a batch is unspecified — a single
  worker handling the whole source SHALL NOT be a violation

### Requirement: Distribution does not wait for the batch-size ramp to climb

Batch sizes grow over the course of a run. The distribution guarantee SHALL
NOT depend on that growth having reached any particular point: the elements
pulled before the ramp has climbed SHALL be spread across workers on the same
terms as the elements pulled after it.

Consequently a source that is exhausted within the ramp's early rounds SHALL
still reach more than one worker, provided it has more elements than
`WORKERS`.

#### Scenario: A source consumed entirely within the first rounds still spreads
- **WHEN** a source small enough to be exhausted before batch size reaches its
  ceiling, but with more elements than `WORKERS`, is run under `.parallel()`
- **THEN** more than one distinct worker thread SHALL have run a batch

### Requirement: The guarantee is distribution, not speedup or even balance

This capability SHALL NOT be read as promising a wall-clock improvement, a
speedup proportional to `WORKERS`, that every worker receives work, or that
workers receive equally sized shares. It promises only that the source is not
funnelled into one worker.

Whether distribution across workers turns into elapsed-time improvement
depends on the interpreter build — bytecode execution is serialised on the
GIL-enabled build and genuinely parallel on the free-threaded build — and on
whether the per-element work outweighs the per-batch dispatch cost. Measured
speedups SHALL be published with the source size and interpreter build they
were measured on, rather than stated as a guarantee.

#### Scenario: A CPU-bound small source improves on the free-threaded build
- **WHEN** a CPU-bound mapping pipeline over a few hundred elements is run
  under `.parallel()` on the free-threaded build and compared against the same
  pipeline under `.sequential()`
- **THEN** the parallel run SHALL be reported as faster, with its source size
  and interpreter build recorded alongside the figure

#### Scenario: The same pipeline on the GIL-enabled build is not a violation
- **WHEN** that same pipeline is run on the GIL-enabled build and shows no
  elapsed-time improvement
- **THEN** the distribution requirement SHALL still hold, and the absence of a
  speedup SHALL NOT be treated as a regression
