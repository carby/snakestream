## ADDED Requirements

### Requirement: The order-blind path SHALL be verified, by observation where the result permits it

Every collector this library ships that declares `UNORDERED` SHALL have its
order-blind path exercised by a verification that fails if a delivery barrier is
reintroduced. Asserting only that the collected result is correct SHALL NOT
count as such a verification: for a collector that genuinely declares
`UNORDERED`, the result is correct under either path, so a correctness assertion
alone passes whether or not the barrier ran and pins nothing.

Verification SHALL be by observation of arrival order wherever the result
permits it. Where a racing source is arranged so that arrival order and
encounter order reliably disagree — for instance one whose early elements are
the expensive ones, so the cheap tail overtakes the slow head — a collector
whose result records the order it was fed SHALL be verified by asserting both
that the result holds every element and that it is **not** in encounter order.

Where the collected result cannot betray arrival order, that observation is
unavailable and SHALL NOT be simulated by a timing measurement. `counting()`
returns the same `int`, and `to_set()` the same `set`, under either path; no
public surface distinguishes them. Such a collector SHALL instead be guarded by
the pair of:

- an assertion that the factory declares `UNORDERED`, which fails if a refactor
  drops the declaration, and
- the existing verification that `collect()` acts on the declaration, which
  fails if a refactor drops the mechanism.

Together these cover both ways the order-blind path can be lost, and neither
depends on a wall-clock threshold. A verification whose outcome depends on
elapsed time SHALL NOT be used for this purpose, because the property under test
is which path ran, not how fast it ran.

#### Scenario: A recording collector is verified by observation
- **WHEN** an ordered racing pipeline over a source whose early elements are
  slow is collected with a collector that declares `UNORDERED` and records the
  order it was fed
- **THEN** the result holds every source element, and its order differs from
  encounter order, demonstrating that no barrier was engaged

#### Scenario: A collector whose result cannot betray arrival order is guarded by declaration and mechanism
- **WHEN** `to_set()`, `counting()`, `summing_int()` or `summarizing_int()` is
  the collector under verification
- **THEN** its factory is asserted to declare `UNORDERED`, and the verification
  that `collect()` acts on that declaration is exercised separately

#### Scenario: A correctness-only assertion does not discharge the requirement
- **WHEN** the only assertion made about an ordered racing pipeline collected
  with an `UNORDERED` collector is that the collected result is correct
- **THEN** the order-blind path is not verified, because that assertion holds
  under both paths

#### Scenario: Timing is not used to decide which path ran
- **WHEN** the order-blind path is verified for any shipped collector
- **THEN** no assertion depends on elapsed wall-clock time
