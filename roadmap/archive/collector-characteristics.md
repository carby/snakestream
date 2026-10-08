+++
id = "collector-characteristics"
title = "`Collector` gains a `characteristics` frozenset and `Characteristics.UNORDERED`"
filed = 2026-08-27
closed = 2026-08-27
outcome = "shipped"
+++

**`Collector` gains a `characteristics` frozenset and `Characteristics.UNORDERED`**
(2026-08-27). Matches OpenJDK's assignments exactly: `to_set()` declares it,
`mapping()`/`collecting_and_then()` derive it from their downstream, and
every other factory — `counting()`, `summing_*`, `averaging_*`,
`summarizing_*`, `to_map()`, `grouping_by()`, `partitioning_by()`,
`min_by`/`max_by` — stays unmarked, matching Java's own choice not this
library's judgment. `grouping_by()`/`partitioning_by()` take a downstream but
deliberately do not derive from it: the downstream's result is a map value,
not the collector's own result. The fifth constructor parameter defaults to
a shared empty `frozenset`, so every existing `Collector(...)` call, in this
library and in user code, is unaffected — additive, not breaking. **Ships
inert**: nothing reads the characteristic yet, and that is stated in the
code, the tests and the README rather than left implicit, so it does not
read as dead code. Was **Now**'s item 1 and **Next**'s item 4 before that.
`openspec validate --strict`, `ruff`, `ty check`, and `pytest
--cov-fail-under=98` (691 passed, 98.30%) all pass. See
`openspec/changes/archive/2026-08-27-add-collector-characteristics`.
