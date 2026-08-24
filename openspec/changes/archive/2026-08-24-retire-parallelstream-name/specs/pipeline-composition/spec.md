## MODIFIED Requirements

### Requirement: Parallel skip() remains globally correct across branches
Under `RACING` execution, the `skip()` step SHALL drop exactly the first `n`
elements pulled across all racing branches combined, not up to `n` elements
per branch. Because branches race independently, "first `n`" means the first
`n` elements pulled across all branches in whatever order the race resolves
them, not necessarily the first `n` elements in source order.

#### Scenario: Parallel skip() does not exceed n dropped in total
- **WHEN** a stream chain containing `.skip(n)` is run under `RACING`
  execution against a source with more than `n` elements, racing across
  multiple branches
- **THEN** the composed output contains exactly `(source length - n)`
  elements in total across all branches, never fewer

#### Scenario: Parallel skip() state resets per composition
- **WHEN** a stream chain containing `.skip(n)` is composed and consumed
  once under `RACING` execution, and then the same chain is composed again
  against a new source
- **THEN** the second composition's shared drop-count starts fresh,
  independent of what any branch observed during the first composition

### Requirement: Parallel branches serialize pulls from the shared upstream source

`race_through()`'s racing branches SHALL NOT call `__anext__()` on the shared upstream source concurrently. Only one branch's pull from the shared source SHALL be in flight at any point in time; each branch's own downstream processing (the intermediate-operation closures applied after the pull) SHALL still be able to run concurrently with other branches' pulls and processing.

#### Scenario: A source with a real await suspension point does not raise

- **WHEN** a stream is run under `RACING` execution over a source whose `__anext__()` contains a genuine `await` suspension point (e.g. `await asyncio.sleep(0)`), and any chain of intermediate operations is composed and consumed
- **THEN** no `RuntimeError: anext(): asynchronous generator is already running` is raised, and all elements the source produces are yielded exactly once in total across all racing branches

#### Scenario: Downstream processing remains concurrent across branches

- **WHEN** a stream chain containing a `map()` step with an `await`-based mapper is run under `RACING` execution against a source with multiple elements
- **THEN** more than one branch's mapper invocation may be in flight concurrently, even though their pulls from the shared upstream source are serialized

#### Scenario: One branch closing the shared source remains safe for other branches

- **WHEN** a stream chain containing `.limit(n)` is run under `RACING` execution against a source with a real `await` suspension point, and racing branch A closes the shared upstream source after the shared count reaches `n`
- **THEN** any other branch subsequently pulling from or closing that same shared source ends its local iteration cleanly (normal end-of-stream), without an unhandled exception escaping `race_through()`'s task loop
