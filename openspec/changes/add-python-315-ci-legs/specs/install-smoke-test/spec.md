## MODIFIED Requirements

### Requirement: CI verifies the built package installs cleanly
The CI workflow SHALL build and install the `snakestream` distribution via `pip install .` into a clean virtual environment, separate from the `uv sync`-managed environment used for the existing test/lint job, for each supported Python version. The supported set is currently Python 3.14 and 3.15, so the job SHALL run two legs, both on the GIL-enabled build; it SHALL remain matrix-shaped so that adding an interpreter is a change to the matrix rather than to the job's structure. A free-threaded build of a supported version SHALL NOT get its own leg while the distribution is a pure-Python, dependency-free wheel, since that leg would install a byte-identical artifact.

#### Scenario: Package installs successfully
- **WHEN** the CI workflow runs `pip install .` against the checked-out repository in a fresh virtual environment
- **THEN** the install SHALL complete without error on every matrix leg (currently Python 3.14 and 3.15)

#### Scenario: Packaging regression fails CI
- **WHEN** a change to `pyproject.toml` or the package layout breaks the build (e.g. the `hatchling.build` backend fails, or an included module is dropped from the built distribution)
- **THEN** the `pip install .` step SHALL fail, causing the CI job to fail

#### Scenario: A newly supported interpreter is covered
- **WHEN** a CPython version comes within `requires-python` and gains a `code_check` leg
- **THEN** that version SHALL also appear as a matrix leg of this job

#### Scenario: An unsupported interpreter is not covered
- **WHEN** the supported floor is raised and an interpreter version leaves `requires-python`
- **THEN** that version SHALL NOT appear as a matrix leg of this job, so the job covers exactly the interpreters the distribution claims to support
