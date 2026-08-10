## Purpose

CI enforcement that a pull request's combined line+branch test coverage of the `snakestream` package does not regress below the configured threshold (currently 98%), so an untested side of a conditional cannot slip through undetected.

## Requirements

### Requirement: Combined line and branch coverage enforcement
CI SHALL fail the build when combined line-and-branch test coverage of the `snakestream` package falls below the configured threshold (98%), not merely when line coverage alone falls below that threshold.

#### Scenario: Fully-covered conditional passes
- **WHEN** a conditional branch (e.g. an `if`/`else`) has both sides exercised by the test suite
- **THEN** the coverage gate does not penalize that conditional and the build passes if overall coverage meets the threshold

#### Scenario: Partially-covered conditional fails the gate
- **WHEN** a conditional branch has only one side exercised by the test suite, dropping combined coverage below 98%
- **THEN** `uv run pytest --cov-fail-under=98` (or the equivalent `coverage.py` invocation) fails the build

### Requirement: Enforcement scope documented
The coverage gate's enforcement mechanism SHALL be documented at its point of configuration so future contributors do not need to re-derive whether branch data is included in the gate.

#### Scenario: Reviewing the coverage configuration
- **WHEN** a contributor reads `[tool.coverage.run]` / `[tool.coverage.report]` in `pyproject.toml`
- **THEN** a comment or the config itself makes clear that `branch = true` combined with the enforced threshold constitutes a combined line+branch gate
