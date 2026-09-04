## MODIFIED Requirements

### Requirement: Awaitability is classified once per composition

For call sites that invoke a user-supplied callable once per element, the dispatch mechanism SHALL determine whether that callable's results require awaiting at most once per composition, and SHALL apply that determination to every subsequent element of the same composition without re-inspecting each result.

The determination SHALL be made by classifying the callable — recognizing both a plain `async def` function and a callable object whose `__call__` is `async def` — and, when that classification says the callable is synchronous, SHALL be confirmed by inspecting the awaitability of the first result actually produced, so that a sync-signatured callable returning a coroutine is still handled correctly.

Under the fork-join executor, a call site invoked once per element runs inside a sink built fresh per element (`execution._run_element`), not once per composition — classifying there, per sink, would reclassify on every element despite the sink being rebuilt, which is what this requirement forbids. Such a call site SHALL instead classify once on the `Op` that owns the callable — at construction, since the callable is fixed for the `Op`'s lifetime — and every sink built from it, whatever executor and however many times it is rebuilt, SHALL reuse that determination rather than recomputing it. `Op` instances are themselves already reused across every composition (`pipeline-composition`), so classifying once there satisfies "at most once per composition" with room to spare rather than exactly.

#### Scenario: Classification is not repeated per element
- **WHEN** a stream operation invokes the same user-supplied callable across many elements of one composition
- **THEN** the awaitability of the callable's results is determined at most once for that composition, not once per element

#### Scenario: Classification does not leak across compositions
- **WHEN** a chain is composed and consumed, and the same chain is then composed and consumed a second time
- **THEN** the second composition performs its own classification independently, and the first composition's classification does not persist into it

#### Scenario: Classification is not repeated per element under the fork-join executor
- **WHEN** a `.parallel()` composition whose chain contains `.map()` and `.filter()` is consumed over many elements spanning more than one batch
- **THEN** the awaitability of each callable is determined once — on the `Op`, at construction — not once per sink and not once per element, matching the count a sequential composition of the same chain produces

#### Scenario: Each parallel branch classifies independently
- **WHEN** a `.parallel()` composition dispatches a callable's chain across more than one batch, each batch building its own sink
- **THEN** every batch's sink for that callable carries the same awaitability determination — not because each batch classifies independently and happens to agree, but because every batch's sink reads the one determination already classified on the shared `Op` it was linked from
