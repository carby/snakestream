## MODIFIED Requirements

### Requirement: Awaitability is classified once per composition

For call sites that invoke a user-supplied callable once per element, the dispatch mechanism SHALL determine whether that callable's results require awaiting at most once per composition, and SHALL apply that determination to every subsequent element of the same composition without re-inspecting each result.

The determination SHALL be made by classifying the callable — recognizing both a plain `async def` function and a callable object whose `__call__` is `async def` — and, when that classification says the callable is synchronous, SHALL be confirmed by inspecting the awaitability of the first result actually produced, so that a sync-signatured callable returning a coroutine is still handled correctly.

#### Scenario: Classification is not repeated per element
- **WHEN** a stream operation invokes the same user-supplied callable across many elements of one composition
- **THEN** the awaitability of the callable's results is determined at most once for that composition, not once per element

#### Scenario: Classification does not leak across compositions
- **WHEN** a chain is composed and consumed, and the same chain is then composed and consumed a second time
- **THEN** the second composition performs its own classification independently, and the first composition's classification does not persist into it

#### Scenario: Each parallel branch classifies independently
- **WHEN** a racing composition fans the chain out across racing branches, each composing its own generator
- **THEN** each branch classifies the callable independently, and every branch reaches the same determination because classification depends only on the callable
