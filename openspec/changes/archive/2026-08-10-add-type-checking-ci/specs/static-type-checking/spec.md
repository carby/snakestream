## ADDED Requirements

### Requirement: CI enforces static type correctness
CI SHALL run a static type checker against `src/snakestream` on at least one Python version in the build matrix and SHALL fail the build when the checker reports type errors.

#### Scenario: Type-consistent code passes
- **WHEN** all type hints in `src/snakestream` are internally consistent with how they're used
- **THEN** the type-check CI step passes

#### Scenario: Type error fails the gate
- **WHEN** a change introduces a type inconsistency (e.g. a function returns a type that violates its declared return annotation)
- **THEN** the type-check CI step fails the build

### Requirement: Type checker selection is evaluated, not assumed
The type checker used for enforcement SHALL be chosen based on a local evaluation against this codebase's `async`/`await`-heavy, `Awaitable`-typed code, not assumed to work without verification.

#### Scenario: Evaluated checker handles the codebase's typing patterns
- **WHEN** the chosen checker runs against `src/snakestream`, including the `Awaitable`-union aliases in `type.py` and the `TYPE_CHECKING`-guarded import in `stream.py`
- **THEN** it produces accurate results without excessive false positives or crashes

#### Scenario: Checker proves unworkable and a fallback is used
- **WHEN** the initially-evaluated checker (`ty`) cannot handle the codebase's typing patterns
- **THEN** an established alternative (`mypy` or `pyright`) is used instead, and the reasoning is recorded
