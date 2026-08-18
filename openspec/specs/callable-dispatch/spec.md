## Purpose

Defines the single dispatch mechanism used to invoke user-supplied callables (predicates, mappers, comparators, consumers, and accumulators) across all stream operations, so that sync functions, `async def` functions, and callable objects with either sync or async `__call__` are all handled correctly and uniformly.

## Requirements

### Requirement: Uniform sync/async callable dispatch
Every stream operation that invokes a user-supplied callable (predicate, mapper, comparator, consumer, or accumulator) SHALL dispatch through a single mechanism that awaits the callable's result whenever that result is awaitable, regardless of whether the callable itself is a plain `async def` function, a plain sync function, or a callable object (a class instance implementing `__call__`, sync or async).

For call sites invoked once per element, the awaitability decision SHALL be made per callable per composition rather than per result, as specified in "Awaitability is classified once per composition" below. For call sites invoked once per composition, dispatch MAY continue to decide per result.

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

#### Scenario: Sync-signatured callable that returns a coroutine
- **WHEN** a stream operation is given a callable whose `__call__` is defined with plain `def` but whose return value is a coroutine
- **THEN** the returned coroutine is awaited before use, producing the real value rather than an un-awaited coroutine object

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
- **WHEN** a `ParallelStream` composition fans the chain out across racing branches, each composing its own generator
- **THEN** each branch classifies the callable independently, and every branch reaches the same determination because classification depends only on the callable

### Requirement: Classification state is per callable

An operation that invokes more than one user-supplied callable per element SHALL classify each of those callables independently, and SHALL NOT share one classification result between them. Each callable's sync-or-async determination applies only to that callable.

This means such an operation supports any mixture of sync and async callables among its parameters, with no constraint that they agree with one another. The homogeneity contract stated in "User-supplied callables must be homogeneous" applies to each individual callable across elements, not across sibling callables.

#### Scenario: to_map with a sync key mapper and an async value mapper
- **WHEN** `to_map(key_mapper, value_mapper)` is given a plain synchronous `key_mapper` and an `async def` `value_mapper`
- **THEN** each element's key is used directly with no `await` and each element's value is awaited, producing a dict of real keys mapped to real values rather than to un-awaited coroutine objects

#### Scenario: to_map with an async key mapper and a sync value mapper
- **WHEN** `to_map(key_mapper, value_mapper)` is given an `async def` `key_mapper` and a plain synchronous `value_mapper`
- **THEN** each element's key is awaited and each element's value is used directly, producing a dict of real keys mapped to real values

#### Scenario: to_map merge function classified separately from its mappers
- **WHEN** `to_map(key_mapper, value_mapper, merge_function)` is given synchronous mappers and an `async def` `merge_function`, and the stream contains two elements producing the same key
- **THEN** the collision is resolved by awaiting `merge_function`, and the mappers are still invoked without `await`

#### Scenario: reducing with a sync mapper and an async binary operator
- **WHEN** `reducing(identity, mapper, binary_operator)` is given a plain synchronous `mapper` and an `async def` `binary_operator`
- **THEN** each element is mapped without `await` and each fold step is awaited, producing the correct reduced value

#### Scenario: reducing with an async mapper and a sync binary operator
- **WHEN** `reducing(identity, mapper, binary_operator)` is given an `async def` `mapper` and a plain synchronous `binary_operator`
- **THEN** each element's mapped value is awaited and each fold step runs without `await`, producing the correct reduced value

### Requirement: User-supplied callables must be homogeneous

A user-supplied callable invoked once per element SHALL be expected to be consistent in whether it returns an awaitable: either every invocation returns an awaitable, or no invocation does. A callable that returns an awaitable for some elements and a plain value for others is NOT supported, and its behavior is undefined.

This narrows a behavior that the previous per-result dispatch mechanism supported incidentally. It has no Java analogue, since Java's functional interfaces cannot vary their return type per invocation.

#### Scenario: Consistently synchronous callable
- **WHEN** a user-supplied callable returns a plain (non-awaitable) value for every element
- **THEN** every element's result is used directly, with no `await`

#### Scenario: Consistently asynchronous callable
- **WHEN** a user-supplied callable returns an awaitable for every element
- **THEN** every element's result is awaited before use

### Requirement: Dispatch specialization does not change operation coverage

`map`, `filter`, `peek`, `sorted` (comparator), `reduce`, `find_any`, `min`/`max`, `for_each`, the `all_match`/`any_match`/`none_match` family, and every collector in `collector.py` that invokes a user-supplied callable SHALL continue to handle all four of the sync-function, async-function, sync-callable-object and async-callable-object cases identically to one another after dispatch is specialized.

#### Scenario: Async callable object still works identically across operations
- **WHEN** an async-`__call__` callable object is passed as the predicate to `filter()`, the mapper to `map()`, the action to `for_each()`, and the mapper to a collector such as `summing_int()` on equivalent streams
- **THEN** all four correctly await the callable's result, producing correct output rather than corrupted or un-awaited values in any one of them
