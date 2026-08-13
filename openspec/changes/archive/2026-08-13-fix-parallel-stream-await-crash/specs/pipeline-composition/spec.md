## ADDED Requirements

### Requirement: Parallel branches serialize pulls from the shared upstream source

`ParallelStream._parallel()`'s racing branches SHALL NOT call `__anext__()` on the shared upstream source concurrently. Only one branch's pull from the shared source SHALL be in flight at any point in time; each branch's own downstream processing (the intermediate-operation closures applied after the pull) SHALL still be able to run concurrently with other branches' pulls and processing.

#### Scenario: A source with a real await suspension point does not raise

- **WHEN** a `ParallelStream` is built over a source whose `__anext__()` contains a genuine `await` suspension point (e.g. `await asyncio.sleep(0)`), and any chain of intermediate operations is composed and consumed
- **THEN** no `RuntimeError: anext(): asynchronous generator is already running` is raised, and all elements the source produces are yielded exactly once in total across all racing branches

#### Scenario: Downstream processing remains concurrent across branches

- **WHEN** a `ParallelStream` chain containing a `map()` step with an `await`-based mapper is composed and consumed against a source with multiple elements
- **THEN** more than one branch's mapper invocation may be in flight concurrently, even though their pulls from the shared upstream source are serialized

#### Scenario: One branch closing the shared source remains safe for other branches

- **WHEN** a `ParallelStream` chain containing `.limit(n)` is composed against a source with a real `await` suspension point, and racing branch A closes the shared upstream source after the shared count reaches `n`
- **THEN** any other branch subsequently pulling from or closing that same shared source ends its local iteration cleanly (normal end-of-stream), without an unhandled exception escaping `ParallelStream._parallel()`'s task loop
