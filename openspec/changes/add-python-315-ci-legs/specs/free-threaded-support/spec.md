## MODIFIED Requirements

### Requirement: CI verifies the library on a free-threaded build
CI SHALL run the test suite against a free-threaded build of each supported interpreter version, in addition to that version's default GIL-enabled build, and SHALL fail the build when the suite fails on any of them.

The library SHALL pass on the free-threaded build without interpreter-conditional code: no `sys._is_gil_enabled()` branch, and no test skipped or xfailed on account of the build.

#### Scenario: The suite passes on both builds
- **WHEN** CI runs the test suite on the GIL-enabled build and on the free-threaded build of each supported interpreter version
- **THEN** every leg SHALL pass, with the same tests running on each

#### Scenario: Every supported version has a free-threaded leg
- **WHEN** a CPython version is within `requires-python` and has a GIL-enabled CI leg
- **THEN** CI SHALL also run a free-threaded leg of that same version

#### Scenario: A free-threading regression fails CI
- **WHEN** a change introduces behaviour that is correct under the GIL but incorrect without it (for example a data race on shared mutable state)
- **THEN** the free-threaded leg SHALL fail, causing the build to fail, even though the GIL leg passes

#### Scenario: Build-conditional code is not the remedy
- **WHEN** the library would need to branch on whether the GIL is enabled in order to pass both legs
- **THEN** that SHALL be treated as a defect to fix rather than a branch to add, since observable behaviour is not permitted to depend on the interpreter build

### Requirement: Checks that do not vary by build run on one leg
Static type checking, dependency vulnerability auditing, and the coverage threshold SHALL run on one leg only: the GIL-enabled leg of the newest supported interpreter version. None of the three varies by interpreter build, so running them on both would consume CI time without being able to report anything the single leg cannot.

Coverage in particular SHALL NOT be treated as build-dependent: it measures identically on the GIL-enabled and free-threaded builds of the same version, so the threshold gains nothing from a second measurement. That claim is about the build, not the version, and the gate runs on the newest version because that is where a new interpreter's tracing first shows up.

#### Scenario: Type checking, audit and coverage run once
- **WHEN** CI runs with GIL-enabled and free-threaded legs for more than one interpreter version
- **THEN** `ty`, the dependency audit and the coverage threshold SHALL each run exactly once, on the GIL-enabled leg of the newest supported version

#### Scenario: Linting and tests still run on every leg
- **WHEN** CI runs with more than one leg
- **THEN** the lint checks, the formatting check and the test suite SHALL run on each leg, since those are the checks capable of differing
