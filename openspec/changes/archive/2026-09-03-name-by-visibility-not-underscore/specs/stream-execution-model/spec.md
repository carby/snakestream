## REMOVED Requirements

### Requirement: PROCESSES is part of the package's public export surface

**Reason**: The requirement describes `PROCESSES` as "the tunable worker count
the racing executor is built from", and it is not tunable by anyone who
imports it. `execution.py` binds `RACING = Racing(PROCESSES)` at import time,
so assigning `snakestream.PROCESSES` after the fact changes nothing a pipeline
does — the export publishes a fact about the implementation, not a lever.

Nothing in the package reads the top-level name, README never shows it in an
import or a code example (it appears once, in a paragraph explaining why the
`.parallel()`/`PROCESSES` naming is deliberately *not* being changed), and
Java's Stream API has no counterpart to be at parity with: parallelism width
lives in `ForkJoinPool.commonPool()`, never on `Stream`.

The `racing-encounter-order` capability already requires that no public name
read or set the in-flight bound, on the grounds that the levers a caller is
given for the cost of racing are `unordered()` and `sequential()`, not a
number. `PROCESSES` is the same kind of import-time-bound constant, and this
removal applies that reasoning consistently.

**Migration**: `from snakestream import PROCESSES` and
`from snakestream.stream import PROCESSES` both raise `ImportError`. The
constant keeps its name and its value in `snakestream.execution`; a caller who
was reading it for information can import it from there. No caller was ever
able to change the worker count by assigning to it, so no working behaviour is
lost. The number of racing branches remains an implementation detail, and the
supported ways to control the cost of racing remain `.sequential()` and
`.unordered()`.
