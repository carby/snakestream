## REMOVED Requirements

### Requirement: An ordered drive is available regardless of stream mode, and find_first() is its only user
**Reason**: `find_first()` was the requirement's only remaining user, and it
stops requesting a single-flight push. Nothing in the library names the
sequential executor for a terminal any more, so the capability the requirement
describes has no callers. The mechanism `find_first()` uses instead —
restoring encounter order at delivery while the chain still races — is
specified by the `racing-encounter-order` capability, which already covers every
other order-observing terminal.

**Migration**: None for the element returned. `find_first()` returns the first
element in encounter order on ordered and unordered pipelines exactly as before.
Callers relying on it to serialize a parallel pipeline — for a side-effecting
chain callable, or to make an order-sensitive operation on an unordered chain
deterministic — SHALL declare `.sequential()`; see the `stream-find-first`
capability.
