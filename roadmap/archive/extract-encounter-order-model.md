+++
id = "extract-encounter-order-model"
title = "The encounter-order model moves into `ordering.py` (`extract-encounter-order-model`)"
filed = 2026-09-03
closed = 2026-09-03
outcome = "shipped"
shipped_as = "extract-encounter-order-model"
+++

**`extract-encounter-order-model`** (2026-09-03) — one concept, the
encounter-order model, was split across two modules that were each about
something else: `Ordering` and `is_ordered()` lived in `sink.py` (subject:
the push protocol), `OrderDemand` and `_split_point()` lived in
`execution.py` (subject: how a chain runs), and both placements were
justified in-source by import topology rather than by concern — each landed
in the deepest module its callers could already reach. The four now live
together in a new `src/snakestream/ordering.py`, which `sink.py` and
`execution.py` import from. A pure module-level move: the same objects, the
same `is` comparisons, the same call sites, resolved at import time. No
behaviour changed, no benchmark was owed (design decision 5, the same
once-per-composition/once-per-terminal argument
`collapse-unseeded-accumulation-rule` made), and no spec delta
(`skip_specs: true`) — no capability under `openspec/specs/` names a module
path for any of the four symbols.

This is the roadmap's first **Done** entry that is a module-boundary move
rather than a duplication collapse — the prior five per-element rejections
and the two prior collapses were all about a rule or a hook stated more than
once, not about where something lives.

**Two consolidations were priced and declined, recorded so neither is
re-derived:** folding the pair down into `sink.py` was rejected on the
concern, not the graph — it would add a *terminal-operation policy* enum
(`OrderDemand`, declared at a `Stream` terminal call site, not by any sink)
to a module whose subject is `begin`/`accept`/`end`, worsening the exact
problem being fixed. Folding the pair up into `execution.py` was rejected on
the graph, not on preference — `ops.py` and `sink.py` both need `Ordering`
and neither may import `execution.py`, which imports `sink.py`; that
direction is an actual cycle, not a judgement call.

**Renamed by `name-by-visibility-not-underscore` (2026-09-03, below):**
`_split_point()` is now bare `split_point()` — the one holdout this entry
left underscored beside bare `is_ordered()` in the same file, closed once
that change's build-time check existed to enforce it either way.
