## Purpose

Declares that `snakestream` is supported on a free-threaded (PEP 779) build of its supported interpreter, states what CI verifies about that, and records the thread-safety properties the library holds today — the written baseline a future parallel executor is built against, rather than an assumption re-derived at that point.

## ADDED Requirements

### Requirement: CI verifies the library on a free-threaded build
CI SHALL run the test suite against a free-threaded build of the supported interpreter, in addition to the default GIL-enabled build, and SHALL fail the build when the suite fails on either. Both builds SHALL be covered by the packaging smoke test as well as the test suite.

The library SHALL pass on the free-threaded build without interpreter-conditional code: no `sys._is_gil_enabled()` branch, and no test skipped or xfailed on account of the build.

#### Scenario: The suite passes on both builds
- **WHEN** CI runs the test suite on the GIL-enabled build and on the free-threaded build of the same interpreter version
- **THEN** both SHALL pass, with the same tests running on each

#### Scenario: A free-threading regression fails CI
- **WHEN** a change introduces behaviour that is correct under the GIL but incorrect without it (for example a data race on shared mutable state)
- **THEN** the free-threaded leg SHALL fail, causing the build to fail, even though the GIL leg passes

#### Scenario: Build-conditional code is not the remedy
- **WHEN** the library would need to branch on whether the GIL is enabled in order to pass both legs
- **THEN** that SHALL be treated as a defect to fix rather than a branch to add, since observable behaviour is not permitted to depend on the interpreter build

### Requirement: Checks that do not vary by build run on one leg
Static type checking, dependency vulnerability auditing, and the coverage threshold SHALL run on the GIL-enabled leg only. None of the three varies by interpreter build, so running them on both would consume CI time without being able to report anything the single leg cannot.

Coverage in particular SHALL NOT be treated as build-dependent: it measures identically on both builds, so the threshold gains nothing from a second measurement.

#### Scenario: Type checking, audit and coverage run once
- **WHEN** CI runs with both a GIL-enabled and a free-threaded leg
- **THEN** `ty`, the dependency audit and the coverage threshold SHALL each run exactly once, on the GIL-enabled leg

#### Scenario: Linting and tests still run on every leg
- **WHEN** CI runs with both legs
- **THEN** the lint checks, the formatting check and the test suite SHALL run on each leg, since those are the checks capable of differing

### Requirement: The library holds no module-level mutable state
No module in `snakestream` SHALL bind mutable state at module scope. Values shared across a pipeline SHALL be either immutable, or owned by an object whose lifetime is one composition.

This is the property that makes the library safe to run on a free-threaded interpreter today, and the one a future parallel executor depends on remaining true.

#### Scenario: Module scope holds no mutable container
- **WHEN** the modules under `snakestream` are inspected for module-scope bindings
- **THEN** none SHALL bind a list, dict, set or other mutable container, and any class-level constant SHALL be an immutable declaration

#### Scenario: Per-composition state does not outlive its composition
- **WHEN** a sink or generator classifies a user callable as sync or async, or accumulates per-element state
- **THEN** that state SHALL belong to an object constructed once per composition, so that two concurrent compositions — whether on one event loop or on separate threads — cannot observe each other's classification or accumulation
