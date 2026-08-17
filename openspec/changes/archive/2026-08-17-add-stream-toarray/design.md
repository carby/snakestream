## Context

Java's `Stream.toArray()` / `toArray(IntFunction<A[]> generator)` materialize a stream into an array. Python has no distinct array type competing with `list`, and no generic-array-construction problem for a factory overload to solve — `list` already is the general-purpose ordered collection `collect(to_list)` returns. The design question (see roadmap.md item #2 and `proposal.md`) is what, if anything, `toArray()` should mean in this codebase; the decision made is: a same-behavior alias for `collect(to_list)`, named `to_array()` to match this codebase's snake_case Java-name adaptations, no factory overload.

## Goals / Non-Goals

**Goals:**
- Add `Stream.to_array()` for Java-surface-API name parity, per this project's stated preference for matching Java Stream naming (`CLAUDE.md`/`README.md` parity table) — adapted to snake_case per every other method in the class (`for_each`, `find_any`, `flat_map`).
- Keep the implementation trivial — no new reduction/collection logic, since `collect(to_list)` already exists and does exactly this.

**Non-Goals:**
- No `toArray(generator)` overload — no Pythonic equivalent to design for.
- No new `Collector`-framework machinery; this is a one-line delegation, not a new collector.

## Decisions

- **`to_array()` delegates to `self.collect(to_list)`.** Alternative considered: duplicate `to_list`'s consume-into-a-list logic inline in `to_array()`. Rejected — delegation keeps a single source of truth for "pull every element into a list" and matches how other trivial terminal ops are expressed in `stream.py`.
- **Named `to_array`, not `toArray`.** Every other Java-derived method name in `stream.py` is already snake_case (`for_each`, `find_any`, `flat_map`, `any_match`), so `toArray` would be the sole camelCase method on the class. `to_array` keeps naming internally consistent while still being recognizable as Java's `toArray()`.
- **No arguments accepted.** Alternative considered: accept an optional factory callable (`to_array(factory=list)`) to leave room for `tuple`/`set`/etc. Rejected per the proposal's decision — that's a different, more speculative feature (effectively `collect(factory)`), not what Java's `toArray(generator)` does, and no one has asked for it. Keeping `to_array()` zero-arg matches Java's no-arg overload exactly and avoids inventing new API surface beyond what's being asked for.
- **Defined once on `Stream`, not overridden on `ParallelStream`.** Matches the existing precedent (`iterator()` in `base_stream.py`) — terminal ops that just drive `self._compose()`/`self.collect()` don't need subclass-specific behavior since `_compose()` is already polymorphic.

## Risks / Trade-offs

- [Risk] Adding a second name for identical behavior (`to_array()` vs. `collect(to_list)`) is minor API-surface duplication. → Mitigation: accepted trade-off for Java parity, consistent with how this project already treats naming parity as a goal in its own right (README parity table, `CLAUDE.md`).
