## Purpose

Defines where `None` sorts relative to non-`None` values when a comparator is
built to tolerate it, covering both a `None` element and a `None` extracted key,
so that ordering a stream containing `None` is expressible rather than a
`TypeError`.

## ADDED Requirements

### Requirement: A comparator can be built to place nulls at either end

Two comparator factories SHALL be provided, one placing `None` before every
non-`None` value and one placing it after. Each SHALL accept an optional
comparator that orders two non-`None` values; when none is supplied, all
non-`None` values SHALL be treated as equivalent to each other, as in Java. The
result SHALL be accepted anywhere a `Comparator` is accepted — sorting, minimum,
maximum, and the minimum/maximum collectors — with no signature change to any of
them.

#### Scenario: Nulls ordered to the front

- **WHEN** a stream containing `None` among comparable values is sorted with a
  nulls-first comparator
- **THEN** every `None` appears before every non-`None` element, and the
  non-`None` elements are in the order the wrapped comparator gives

#### Scenario: Nulls ordered to the back

- **WHEN** the same stream is sorted with a nulls-last comparator
- **THEN** every `None` appears after every non-`None` element, and the
  non-`None` elements are in the order the wrapped comparator gives

#### Scenario: No wrapped comparator supplied

- **WHEN** a nulls-first comparator is built with no wrapped comparator and used
  to sort
- **THEN** the `None` elements are ordered to the front and all non-`None`
  elements compare equal to one another, keeping their encounter order

#### Scenario: Accepted by a non-sorting consumer

- **WHEN** a nulls-first comparator is passed to the minimum terminal over a
  stream containing `None`
- **THEN** `None` is returned as the minimum, rather than a `TypeError` being
  raised

### Requirement: Null tolerance applies to an extracted key as well as an element

When a nulls-tolerating comparator wraps a key-based comparator, the tolerance
SHALL apply to each segment's extracted key: an element whose key is `None`
SHALL order at the same end as a `None` element would, and two elements whose
keys are both `None` SHALL compare equal on that segment and fall through to the
next one. Extracting a key from a `None` element SHALL NOT be attempted.

#### Scenario: Records with a missing field sort without raising

- **WHEN** a stream of records is sorted by a key-based comparator made
  nulls-last, and some records' keys are `None`
- **THEN** the records with a `None` key appear last, the rest are ordered by
  their keys, and no `TypeError` is raised

#### Scenario: A null key falls through to the tie-break segment

- **WHEN** a two-segment chain is made nulls-tolerant and two elements both have
  `None` for the first segment's key
- **THEN** the two elements are ordered by the second segment

#### Scenario: A null element is not passed to a key extractor

- **WHEN** a stream containing a `None` element is sorted by a nulls-first
  key-based comparator
- **THEN** the `None` element sorts to the front and the key extractor is never
  invoked with `None`

### Requirement: Null tolerance composes with chaining and reversal

A nulls-tolerating key-based comparator SHALL remain composable: appending a
tie-break ordering and reversing SHALL both continue to work and SHALL each
return a new comparator without mutating the receiver. Reversing a nulls-first
ordering SHALL place nulls last, and reversing a nulls-last ordering SHALL place
them first, matching Java.

#### Scenario: Reversal moves the nulls to the other end

- **WHEN** a nulls-first comparator is reversed and used to sort a stream
  containing `None`
- **THEN** the `None` elements appear last and the non-`None` elements are in the
  negated order

#### Scenario: Composition does not mutate the receiver

- **WHEN** a nulls-tolerant comparator is extended with a tie-break ordering
- **THEN** a new comparator is returned and sorting with the original comparator
  still gives the original order

### Requirement: The sorting path and the direct-comparison path agree

The ordering a nulls-tolerating comparator imposes when it is used to sort SHALL
be identical to the ordering it imposes when it is invoked directly as a
two-argument comparator, including for `None` values, for elements that compare
equal, and for every combination of null placement and reversal.

#### Scenario: Both paths agree on the same input

- **WHEN** the same nulls-tolerating comparator is used to sort a list and,
  separately, to compare the same elements pairwise
- **THEN** the pairwise signs are consistent with the sorted order, `None`
  included

#### Scenario: Ties keep encounter order

- **WHEN** a stream containing several `None` elements and several elements the
  wrapped comparator treats as equal is sorted
- **THEN** elements that compare equal, `None`s included, keep the relative order
  they entered with
