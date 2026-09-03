## Purpose

One rule for what a leading underscore means on a module-level name in
`src/snakestream` — it marks a name used only inside its own module, never
"not part of the public API" — together with the build check that keeps the
rule from drifting back, so that a contributor reading any module can tell
from the name alone whether another module depends on it.

## ADDED Requirements

### Requirement: A leading underscore marks module-local use, not API status

A module-level name in `src/snakestream` SHALL carry a leading underscore if
and only if no other module in `src/snakestream` uses it. A name that another
module in the package imports SHALL be bare, and a name that no other module
imports and that no caller reaches as part of the documented API SHALL be
underscored.

The underscore SHALL NOT be used to express that a name is absent from the
package's public API. Every module below `snakestream/__init__.py` is an
implementation detail, so that distinction carries no information at
module-level and its absence SHALL NOT be read as a promise that a bare name
is public.

This rule governs module-level names — functions, classes, constants and type
variables. It does not govern class members, where a leading underscore
remains the only marker Python offers and continues to mean "not for callers".

#### Scenario: A name is imported by another module in the package

- **WHEN** a module under `src/snakestream` imports a name from another module
  in the package
- **THEN** that name is bare, and the importing module names it without a
  leading underscore

#### Scenario: A helper is used only where it is defined

- **WHEN** a module-level function, class or constant is referenced only
  within the module that defines it, and no caller reaches it as documented API
- **THEN** it carries a leading underscore

#### Scenario: A caller-facing name is never imported inside the package

- **WHEN** a name is part of the documented API — a collector factory, a
  comparator factory, an exception type, `Stream` itself — and no module in
  `src/snakestream` imports it, because callers import it instead
- **THEN** it is bare, and its absence from the package's internal import
  graph does not make it a candidate for an underscore

#### Scenario: A class member stays private with an underscore

- **WHEN** a method or attribute on an exported class is not intended for
  callers
- **THEN** it keeps its leading underscore, regardless of which modules use it,
  since no package-level export list can hide a member

### Requirement: Tests may reach into private names

A module under `tests/` SHALL be permitted to import any name from
`src/snakestream`, including an underscore-prefixed one. Such an import is
white-box testing and SHALL NOT be treated as a violation of the naming rule,
and SHALL NOT be counted as making the imported name non-local for the purpose
of deciding whether it carries an underscore.

#### Scenario: A test imports a module-local helper

- **WHEN** a test imports an underscore-prefixed name from a module in the
  package in order to exercise it directly
- **THEN** the naming check does not report it, and the name keeps its
  underscore

### Requirement: The build reports a private name crossing a module boundary

The test suite SHALL include a check that fails when any module under
`src/snakestream` imports an underscore-prefixed name from another module in
`src/snakestream`. The check SHALL read the package's own import statements
rather than a maintained list of names, so that a name added later is covered
without anyone remembering to register it.

The failure SHALL name the importing module, the defining module and the name,
so that the reported fix is either to drop the underscore or to stop crossing
the boundary.

#### Scenario: A cross-module private import is introduced

- **WHEN** a change makes one module in `src/snakestream` import an
  underscore-prefixed name from another module in the package
- **AND** the test suite runs
- **THEN** the check fails and reports the importing module, the defining
  module and the name

#### Scenario: The package satisfies the rule

- **WHEN** every cross-module import in `src/snakestream` names a bare name
- **THEN** the check passes, and it imposes no suppression or exemption on any
  module

#### Scenario: A test's private import does not fail the check

- **WHEN** a module under `tests/` imports an underscore-prefixed name from the
  package
- **THEN** the check does not report it, since it inspects only modules under
  `src/snakestream`
