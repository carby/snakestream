## MODIFIED Requirements

### Requirement: The lint gate enforces bug, simplification, performance and modernization rules
Beyond syntax and undefined-name checks, the rule selection SHALL include the
likely-bug, simplification, comprehension, ruff-specific, performance,
return-value, misc-lint, modernization and pylint-derived families, so that
hand-rolled equivalents of builtins and stdlib constructs, mutable-looking call
defaults, and mid-union `None` are reported by the build.

The selection SHALL additionally include the pytest-specific family, whose
rules fire only on test files and which covers assertion and `raises` forms
that no other family inspects.

#### Scenario: A hand-rolled equivalent of a builtin is reported
- **WHEN** code in `src/snakestream` reimplements something the interpreter or standard library already provides and a selected rule covers it
- **THEN** the lint step reports it and fails the build

#### Scenario: The gate is applied over the package source
- **WHEN** the lint step runs in CI
- **THEN** the widened selection is enforced over `src/snakestream` on every matrix leg, alongside the existing formatting check

#### Scenario: The gate is applied over the test suite
- **WHEN** the lint step runs in CI
- **THEN** the same selection is enforced over `tests/` as over `src/snakestream`, save for individually named rule exemptions
- **AND** a lint violation introduced in a test file fails the build exactly as one in the package source does

## ADDED Requirements

### Requirement: A per-path exemption names the rule, not the rule set
Where a selected rule is wrong for a whole class of files rather than for one
line, the exemption SHALL name the individual rule for that path, and SHALL NOT
disable a family or a list of families wholesale. The reason SHALL be recorded
at the exemption, as it is for an inline suppression.

#### Scenario: A rule that contradicts a file class is exempted narrowly
- **WHEN** a rule's finding is a false positive for every file of a given kind
- **THEN** that single rule is exempted for that path with its reason recorded
- **AND** every other rule in its family remains enforced over those files

#### Scenario: Comparison literals in tests are not treated as magic values
- **WHEN** a test compares against a literal, as in an assertion or a predicate under test
- **THEN** the magic-value rule does not report it, since the literal is the test's data and naming it would obscure the assertion
- **AND** that same rule remains enforced over `src/snakestream`

### Requirement: Test failure guards report, and do not depend on assertion rewriting
A test that guards a branch it must not reach SHALL fail through a call that
raises, carrying a message naming what did not happen, rather than through a
bare assertion on a false constant. A bare assertion there reports nothing when
it fires, and it executes only while assertion rewriting is enabled for the file
it lives in: with rewriting disabled, or in a helper module the test framework
does not rewrite, an optimized interpreter removes it and the guarded branch
passes silently.

#### Scenario: A guarded branch is reached without assertion rewriting
- **WHEN** the guarded branch is reached while assertions are disabled and the framework's assertion rewriting is not in effect
- **THEN** the test fails, rather than passing because the guard was removed

#### Scenario: The failure says what did not happen
- **WHEN** such a guard fires
- **THEN** the reported failure names the expectation that was violated, rather than only the location of the guard

### Requirement: An expected-exception assertion identifies the exception it expects
A test asserting that an operation raises SHALL constrain the assertion enough
to distinguish the exception it provoked from an unrelated one of the same
type, by matching its message or by naming a type only that operation raises.

#### Scenario: An unrelated exception of the same type does not satisfy the test
- **WHEN** a test asserts that a user callback's exception propagates through a pipeline
- **AND** a different fault raises the same exception type from elsewhere in that pipeline
- **THEN** the assertion does not accept it as the expected failure
