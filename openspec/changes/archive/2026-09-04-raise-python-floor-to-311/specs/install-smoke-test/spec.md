## MODIFIED Requirements

### Requirement: CI verifies the built package installs cleanly
The CI workflow SHALL build and install the `snakestream` distribution via `pip install .` into a clean virtual environment, separate from the `uv sync`-managed environment used for the existing test/lint job, for each supported Python version (3.11–3.14).

#### Scenario: Package installs successfully
- **WHEN** the CI workflow runs `pip install .` against the checked-out repository in a fresh virtual environment
- **THEN** the install SHALL complete without error on every matrix leg (Python 3.11, 3.12, 3.13, 3.14)

#### Scenario: Packaging regression fails CI
- **WHEN** a change to `pyproject.toml` or the package layout breaks the build (e.g. `setuptools.build_meta` fails, or an included module is dropped from the built distribution)
- **THEN** the `pip install .` step SHALL fail, causing the CI job to fail

#### Scenario: An unsupported interpreter is not covered
- **WHEN** the supported floor is raised and an interpreter version leaves `requires-python`
- **THEN** that version SHALL NOT appear as a matrix leg of this job, so the job covers exactly the interpreters the distribution claims to support
