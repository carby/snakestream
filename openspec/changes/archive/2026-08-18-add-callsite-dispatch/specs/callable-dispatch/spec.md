## ADDED Requirements

### Requirement: Classification state is per callable

An operation that invokes more than one user-supplied callable per element SHALL
classify each of those callables independently, and SHALL NOT share one
classification result between them. Each callable's sync-or-async determination
applies only to that callable.

This means such an operation supports any mixture of sync and async callables
among its parameters, with no constraint that they agree with one another. The
homogeneity contract stated in "User-supplied callables must be homogeneous"
applies to each individual callable across elements, not across sibling
callables.

#### Scenario: to_map with a sync key mapper and an async value mapper
- **WHEN** `to_map(key_mapper, value_mapper)` is given a plain synchronous
  `key_mapper` and an `async def` `value_mapper`
- **THEN** each element's key is used directly with no `await` and each element's
  value is awaited, producing a dict of real keys mapped to real values rather
  than to un-awaited coroutine objects

#### Scenario: to_map with an async key mapper and a sync value mapper
- **WHEN** `to_map(key_mapper, value_mapper)` is given an `async def` `key_mapper`
  and a plain synchronous `value_mapper`
- **THEN** each element's key is awaited and each element's value is used
  directly, producing a dict of real keys mapped to real values

#### Scenario: to_map merge function classified separately from its mappers
- **WHEN** `to_map(key_mapper, value_mapper, merge_function)` is given
  synchronous mappers and an `async def` `merge_function`, and the stream
  contains two elements producing the same key
- **THEN** the collision is resolved by awaiting `merge_function`, and the
  mappers are still invoked without `await`

#### Scenario: reducing with a sync mapper and an async binary operator
- **WHEN** `reducing(identity, mapper, binary_operator)` is given a plain
  synchronous `mapper` and an `async def` `binary_operator`
- **THEN** each element is mapped without `await` and each fold step is awaited,
  producing the correct reduced value

#### Scenario: reducing with an async mapper and a sync binary operator
- **WHEN** `reducing(identity, mapper, binary_operator)` is given an `async def`
  `mapper` and a plain synchronous `binary_operator`
- **THEN** each element's mapped value is awaited and each fold step runs without
  `await`, producing the correct reduced value
