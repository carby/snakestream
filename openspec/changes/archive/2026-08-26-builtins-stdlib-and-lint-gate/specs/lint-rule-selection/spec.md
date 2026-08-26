## Purpose

CI enforcement of a lint rule set over `src/snakestream` that goes beyond
syntax errors and unused names — covering async-correctness, likely-bug,
simplification, performance and modernization families — so that the classes of
finding a human review pass keeps rediscovering are caught by the build instead,
and so that every suppression records why the rule is wrong here.

## ADDED Requirements

### Requirement: The lint gate enforces async-correctness rules
The configured ruff rule selection SHALL include the async-correctness family
(`ASYNC`), so that misuse of `async`/`await` in `src/snakestream` fails the
build rather than being caught only by review. This is the family the library's
entire surface is built from, and it SHALL be enforced even though it reports no
findings against the code as it stands.

#### Scenario: Async-correctness violation fails the gate
- **WHEN** a change to `src/snakestream` introduces a construct the async-correctness rules reject
- **THEN** `uv run ruff check .` exits non-zero and the CI lint step fails the build

#### Scenario: Clean async code passes
- **WHEN** `src/snakestream` contains no async-correctness violation
- **THEN** the lint step passes, and enabling the family imposes no suppression or rewrite on existing code

### Requirement: The lint gate enforces bug, simplification, performance and modernization rules
Beyond syntax and undefined-name checks, the rule selection SHALL include the
likely-bug, simplification, comprehension, ruff-specific, performance,
return-value, misc-lint, modernization and pylint-derived families, so that
hand-rolled equivalents of builtins and stdlib constructs, mutable-looking call
defaults, and mid-union `None` are reported by the build.

#### Scenario: A hand-rolled equivalent of a builtin is reported
- **WHEN** code in `src/snakestream` reimplements something the interpreter or standard library already provides and a selected rule covers it
- **THEN** the lint step reports it and fails the build

#### Scenario: The gate is applied over the package source
- **WHEN** the lint step runs in CI
- **THEN** the widened selection is enforced over `src/snakestream` on every matrix leg, alongside the existing formatting check

### Requirement: Suppressions carry the reason they are correct
Where a selected rule produces a finding that is wrong for this codebase, the
finding SHALL be suppressed at its site with an inline suppression naming the
rule and stating why it does not apply, rather than by removing the rule from
the selection or by changing correct code to satisfy it.

#### Scenario: A false positive is suppressed in place
- **WHEN** a selected rule flags a line whose behavior is deliberate and correct
- **THEN** that line carries a rule-specific inline suppression with a stated reason
- **AND** the rule remains enabled for the rest of the package

#### Scenario: A rule is not disabled to avoid a question
- **WHEN** a selected rule raises a finding whose correctness is arguable
- **THEN** the finding is resolved in the code or suppressed with a reason
- **AND** the rule SHALL NOT be dropped from the selection to make the finding disappear

### Requirement: A shared default value is named where the default is written
Where a public factory takes a collector as an optional argument, the default
SHALL be a named, module-level value rather than a call evaluated in the
signature, so that a reader can see at the default site that the value is
stateless and safe to share across every call.

#### Scenario: Reading a factory's signature
- **WHEN** a contributor reads the signature of a collector factory that takes an optional downstream collector
- **THEN** the default is a named shared value, not a constructor call, and no suppression is needed to explain it

#### Scenario: The shared default behaves as the per-call default did
- **WHEN** two separate collections run through such a factory without passing a downstream collector
- **THEN** each collection produces its own independent result, exactly as when the default was evaluated per call
