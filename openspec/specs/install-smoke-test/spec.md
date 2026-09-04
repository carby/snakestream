## Purpose

CI verification that the packaged `snakestream` distribution installs cleanly via `pip install .` and that `import snakestream` succeeds against the installed package, run across the full supported Python matrix — catching packaging mistakes (missing package/include entries, broken dynamic version resolution, dev-only dependencies leaking into the built distribution) that `uv sync` against checked-out source would never surface.

## Requirements

### Requirement: CI verifies the built package installs cleanly
The CI workflow SHALL build and install the `snakestream` distribution via `pip install .` into a clean virtual environment, separate from the `uv sync`-managed environment used for the existing test/lint job, for each supported Python version (3.13–3.14).

#### Scenario: Package installs successfully
- **WHEN** the CI workflow runs `pip install .` against the checked-out repository in a fresh virtual environment
- **THEN** the install SHALL complete without error on every matrix leg (Python 3.13, 3.14)

#### Scenario: Packaging regression fails CI
- **WHEN** a change to `pyproject.toml` or the package layout breaks the build (e.g. `setuptools.build_meta` fails, or an included module is dropped from the built distribution)
- **THEN** the `pip install .` step SHALL fail, causing the CI job to fail

#### Scenario: An unsupported interpreter is not covered
- **WHEN** the supported floor is raised and an interpreter version leaves `requires-python`
- **THEN** that version SHALL NOT appear as a matrix leg of this job, so the job covers exactly the interpreters the distribution claims to support

### Requirement: CI verifies the installed package imports successfully
After installing the built distribution, the CI workflow SHALL run `import snakestream` from outside the repository's source tree and SHALL fail the job if the import raises an error.

#### Scenario: Import succeeds against the installed package, not local source
- **WHEN** the CI workflow runs `python -c "import snakestream"` from a working directory other than the repository root, after `pip install .` has completed
- **THEN** the import SHALL succeed by resolving `snakestream` from the installed distribution
- **AND** the check SHALL NOT pass merely because Python resolved the package from the repository's `src/` layout via an accidental `sys.path` entry

#### Scenario: Import-time regression fails CI
- **WHEN** the installed package raises an exception on `import snakestream` (e.g. a missing dependency declared incorrectly, or a broken module-level statement)
- **THEN** the CI job SHALL fail
