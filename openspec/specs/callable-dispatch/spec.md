## Purpose

Defines the single dispatch mechanism used to invoke user-supplied callables (predicates, mappers, comparators, consumers, and accumulators) across all stream operations, so that sync functions, `async def` functions, and callable objects with either sync or async `__call__` are all handled correctly and uniformly.

## Requirements

### Requirement: Uniform sync/async callable dispatch
Every stream operation that invokes a user-supplied callable (predicate, mapper, comparator, consumer, or accumulator) SHALL dispatch through a single mechanism that awaits the callable's result whenever that result is awaitable, regardless of whether the callable itself is a plain `async def` function, a plain sync function, or a callable object (a class instance implementing `__call__`, sync or async).

#### Scenario: Sync function callable
- **WHEN** a stream operation is given a plain synchronous function as its callable
- **THEN** the function is called and its return value is used directly, with no `await`

#### Scenario: Async function callable
- **WHEN** a stream operation is given an `async def` function as its callable
- **THEN** the function is called and its result is awaited before use

#### Scenario: Sync callable object
- **WHEN** a stream operation is given an instance of a class whose `__call__` is defined with plain `def` (not `async def`)
- **THEN** the instance is called and its return value is used directly, with no `await`

#### Scenario: Async callable object
- **WHEN** a stream operation is given an instance of a class whose `__call__` is defined with `async def`
- **THEN** the instance is called and the resulting coroutine is awaited before use, producing the real value rather than an un-awaited coroutine object

### Requirement: Dispatch mechanism is consistent across operations
`map`, `filter`, `peek`, `sorted` (comparator), `reduce`, `find_any`, `min`/`max`, `for_each`, and the `all_match`/`any_match`/`none_match` family SHALL use the same dispatch mechanism for invoking their user-supplied callables, so that async-callable-object support is uniform rather than present in some operations and missing in others.

#### Scenario: Async callable object works identically across operations
- **WHEN** an async-`__call__` callable object is passed as the predicate to `filter()`, the mapper to `map()`, and the action to `for_each()` on equivalent streams
- **THEN** all three operations correctly await the callable's result in each case, producing correct output rather than corrupted/un-awaited values in any one of them

### Requirement: flat_map's up-front coroutine rejection is unaffected
`flat_map`'s existing check that rejects a mapper whose direct return value is itself a coroutine (signaling the caller passed an `async def` generator-producing function incorrectly) SHALL remain a separate, pre-call classification distinct from the general dispatch mechanism, and SHALL NOT be folded into or replaced by it.

#### Scenario: flat_map still rejects a coroutine-returning mapper
- **WHEN** `flat_map()` is given a mapper whose invocation returns a bare coroutine rather than an iterable/async-iterable of sub-elements
- **THEN** `flat_map()` raises the same error it does today, independent of any change to the general callable-dispatch mechanism
