## Purpose

Defines `StreamBuilder`, Java's `Stream.Builder`-equivalent — an accumulator that collects elements one at a time via `add()`/`accept()` and then produces a `Stream` over a snapshot of those elements via `build()`.

## Requirements

### Requirement: add()/accept() append an element to the builder

`StreamBuilder.add(element)` and `StreamBuilder.accept(element)` SHALL append `element` to the builder's internal element list. `add()` SHALL return the same builder instance to support chaining; `accept()` SHALL return `None`, matching Java's `Stream.Builder.accept(T)` void-return contract.

#### Scenario: add() chains and accumulates elements in order

- **WHEN** `builder.add(1).add(2).add(3)` is called
- **THEN** the builder's elements are `[1, 2, 3]`, in that order, and each `add()` call returns the same builder instance

#### Scenario: accept() accumulates without returning the builder

- **WHEN** `builder.accept(1)` is called
- **THEN** the builder's elements include `1`, and the call returns `None`

### Requirement: build() produces a stream over a snapshot of the builder's elements

`StreamBuilder.build()` SHALL construct a `Stream` over a snapshot (copy) of the builder's current elements, not a reference to the builder's live internal list. Elements added to the builder via `add()`/`accept()` after `build()` has been called SHALL NOT appear in the previously-built stream.

#### Scenario: build() captures elements added before it was called

- **WHEN** `builder.add(1).add(2)` is called, then `stream = builder.build()`
- **THEN** consuming `stream` yields `[1, 2]`

#### Scenario: Elements added after build() do not leak into the built stream

- **WHEN** `builder.add(1).add(2)` is called, then `stream = builder.build()`, then `builder.add(3)` is called
- **THEN** consuming `stream` still yields `[1, 2]`, not `[1, 2, 3]`
