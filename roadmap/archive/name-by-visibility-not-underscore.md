+++
id = "name-by-visibility-not-underscore"
title = "A leading underscore means module-local, not private (`name-by-visibility-not-underscore`)"
filed = 2026-09-03
closed = 2026-09-03
outcome = "shipped"
shipped_as = "name-by-visibility-not-underscore"
+++

**`name-by-visibility-not-underscore`** (2026-09-03) — the leading
underscore on a module-level name in `src/snakestream` had been doing the
work of a public-API marker in a package that has no public API to mark:
every module below `snakestream/__init__.py` is already an implementation
detail, so 27 names were underscored *and* imported by another module in
the package — a contradiction in terms, worst on `ordering.py`, extracted
three days earlier, which held `is_ordered()` bare and `_split_point()`
underscored side by side with nothing distinguishing them but which module
each had come from.

**The rule, adopted:** a module-level name carries a leading underscore iff
no other module in `src/snakestream` uses it; a name reachable only through
a module path or the package's `__init__.py` export list is bare regardless
of whether anything inside the package imports it; `tests/` may import
anything, which is white-box testing and not a violation. Applied as three
stories: **27 renames** (the contradiction above, dropped one direction),
**8 renames the other way** (`execution.py`'s `stream_through`,
`group_through`, `race_through`, `feed_through`, `drain`, `Sequential`,
`Racing` and `sort.py`'s `merge_sort`, each used only in its own module and
reachable by no caller — so the rule reads in both directions rather than
only ever removing underscores, which is how `ordering.py` got into this
state in the first place), and **one export removed**: `PROCESSES`, cut
from `snakestream/__init__.py` and `stream.py`'s re-export, because it was
never a tunable lever — `execution.py` binds `RACING` from it at import
time, so assigning to the exported name changed nothing a pipeline did —
and the same reasoning the `racing-encounter-order` capability already
applies to `_IN_FLIGHT_PER_WORKER` (no public name for an import-time-bound
constant) now applies to both. Supersedes the 2026-08-24 entry below that
added the export.

The decidable half of the rule — underscored-and-imported-elsewhere — is
now enforced by `tests/test_name_visibility.py`, an AST check with no
maintained name list to fall out of date; the other half (a bare name
really is caller-facing) is a one-time judgment with no mechanical check,
since there is no maintained list of caller-facing names to check it
against without the `__init__.py`-as-boundary move this rejected.

**Two design questions answered, so neither is re-opened:**
Making `__init__.py` the public boundary instead — re-exporting the ~40
caller-facing names and treating every module path as internal — was
rejected: it cannot be enforced (nothing stops `from snakestream.collectors
import to_list` regardless of what `__init__.py` exports), and it would
re-break the `collector`/`collectors` split done three weeks earlier for
the opposite reason. Ruff's `PLC2701` (import-private-name) is exactly this
rule and was rejected for now, not permanently: it is preview-only, so
enabling it changes the behaviour of all fifteen rule families this
project already selects, not just the one being added; and it skips
imports used only in annotations, which would have missed `_Aiter` — one
of the 27. Revisit when `PLC2701` stabilises, per the `lint-rule-selection`
capability's per-rule-exemption pattern.

1000 tests green (997 + 3 for the new check), coverage held at the
baseline figure exactly (98.61%, `--cov-fail-under=98`), `ruff`,
`ruff format --check` and `ty check src` all pass. `PROCESSES` is the one
loud break (`ImportError` at the import site); everything else is
caller-invisible by construction — same objects, same `is` comparisons,
same call sites, resolved at import time.

**One design-doc claim, priced during implementation and found not to
hold, recorded so it is not re-asserted:** the design took `_UNSET` -> 
`UNSET` as, independent of the rule, "a small correctness win" because the
sentinel is a public factory argument's default (`reducing(identity=_UNSET,
...)`) and so "already rendered to users by `help()`". Checked against both
`inspect.signature()` and `pydoc.render_doc()`, before and after the
rename: both show the sentinel's raw `object()` repr (`<object object at
0x...>`) in either case, never the variable name that held it at
definition. The rename is still correct — `UNSET` is genuinely
cross-module and the rule requires it bare regardless — but the
independent correctness win the design claimed for it does not exist.
