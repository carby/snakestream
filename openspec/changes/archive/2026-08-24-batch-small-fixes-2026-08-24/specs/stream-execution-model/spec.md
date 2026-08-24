## ADDED Requirements

### Requirement: PROCESSES is part of the package's public export surface

`PROCESSES`, the tunable worker count the racing executor is built from, SHALL
be importable directly from the top-level `snakestream` package, not only from
`snakestream.execution`.

#### Scenario: PROCESSES is importable from the top-level package

- **WHEN** a caller writes `from snakestream import PROCESSES`
- **THEN** the import succeeds and yields the same `int` value as
  `snakestream.execution.PROCESSES`
