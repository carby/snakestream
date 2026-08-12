## Context

`BaseStream`/`Stream`/`ParallelStream` (`base_stream.py`, `stream.py`, `parallel_stream.py`) are plain classes. `type.py` already defines `T`/`R` `TypeVar`s and generic-looking aliases (`Mapper = Callable[[T], R | None]`, `Predicate = Callable[[T], bool | Awaitable[bool]]`, etc.), and `StreamBuilder` is already `Generic[T]` — but nothing on the `Stream` class itself binds `T`, so every method signature that references `T`/`R` is checking the *callable's* shape correctly while leaving the *stream's* own element type as `Unknown`. `ty` (CI's type checker, see `static-type-checking` capability) doesn't flag `Stream.of([1,2,3]).map(lambda s: s.upper())`.

The chain-of-closures model (`CLAUDE.md`) is intentionally mutation-based: every intermediate op does `self._chain.append(fn); return self`. This is the load-bearing constraint for this design — a "real" `map(Mapper[T, R]) -> Stream[R]` would, in an immutable-pipeline design, return a *new* `Stream[R]` instance. Here it returns the *same* `self` object, whose runtime type doesn't and can't change. The roadmap separately tracks "mutable-builder vs immutable-pipeline semantics" as its own decision (`Next`, high blast radius); this change does not revisit that decision — it works within the current mutation-based model.

## Goals / Non-Goals

**Goals:**
- `Stream[T]` (and `BaseStream[T]`, `ParallelStream[T]`) correctly propagate element type through `map`/`flat_map` (type-changing) and `filter`/`distinct`/`peek`/`limit`/`sorted` (type-preserving) so `ty` can catch element-type misuse.
- Terminal ops (`collect`, `reduce`, `for_each`, `find_any`, `min`/`max`, `all_match`/`any_match`/`none_match`, `count`) are typed against the stream's bound `T`.
- `StreamBuilder[T].build()` returns `Stream[T]`, not a bare `Stream`.
- `ty` passes on the resulting code with no new suppressions beyond the one narrowly-scoped cast described below.

**Non-Goals:**
- No runtime behavior change. This is a typing-only change; method bodies are untouched.
- No change to the mutable chain-of-closures model (`self._chain.append(fn); return self`) — that's the separate "mutable-builder vs immutable-pipeline" roadmap item.
- No `Hashable` bound (or other constraint) added to `T` for `distinct()` — out of scope; see Open Questions.
- No change to `ParallelStream`'s racing/ordering semantics.

## Decisions

**1. `BaseStream`, `Stream`, `ParallelStream` become `Generic[T]`.**
`ParallelStream(Stream[T])` inherits the parameter through normal subclassing — no separate generic machinery needed there.

**2. `map`/`flat_map` are typed to return `Stream[R]`, implemented via `cast(Stream[R], self)`.**
Since the runtime object is the *same* mutated `self` (a `Stream[T]` becoming, for typing purposes, a `Stream[R]`), there's no way to satisfy this without either (a) fabricating a new instance at runtime — rejected, it's a behavior change and duplicates the separate mutable-vs-immutable roadmap decision — or (b) a type-level cast at the return statement. `cast()` is the standard, narrowly-scoped tool for "the type checker can't derive this, but I know it's correct from the calling contract": `map(mapper: Mapper[T, R]) -> Stream[R]` is true *as long as* nothing else holds a `Stream[T]`-typed reference to the same object across the call and expects it to stay `Stream[T]` — which matches the existing fluent-chaining usage pattern (`stream.map(...).filter(...).collect(...)`) but not the "keep a `Stream[T]` variable around and call `.map()` on it later expecting the original binding to still type-check as `T`" pattern. This is a known, acceptable sharp edge of typing a mutating fluent builder and is called out in Risks below.
Alternative considered: leave `map`/`flat_map` returning `Stream[T]` (i.e., don't change element type at the type level) — rejected, it defeats the purpose of the change; a `Stream[int].map(str_upper)` would still type-check as `Stream[int]`, which is the exact bug this change exists to fix.

**3. Type-preserving intermediaries (`filter`, `distinct`, `peek`, `limit`, `sorted`) keep `Stream[T]` return type — no cast needed**, since `self` genuinely stays `Stream[T]` for these.

**4. `StreamBuilder.build()` fixed to `-> Stream[T]`.**
`StreamBuilder` is already `Generic[T]` and holds `self._elements: list[T]`; `build()` returning a bare `Stream` was simply dropping the parameter it already had in hand. No `cast` needed — `Stream(self._elements)` can be typed directly against `Stream[T]`.

**5. `type.py` aliases are unchanged.**
`Mapper`, `FlatMapper`, `Predicate`, `Comparator`, `Consumer`, `Accumulator` already reference `T`/`R` correctly; the gap was purely that `Stream` itself never bound `T`. Confirmed by re-reading each alias — none need restructuring.

**6. Internal `self._chain: list[Callable]` stays untyped (`Callable`, not `Callable[[T], R]`).**
The chain holds heterogeneous closures across a pipeline's lifetime (a `map` closure next to a `filter` closure next to a `sorted` closure), so a single element-type parameter can't describe it — and it's a private implementation detail, not part of the public contract this change targets. Only method *signatures* (the public boundary) are parameterized.

## Risks / Trade-offs

- **[Risk]** The `cast()` in `map`/`flat_map` means `ty` cannot actually verify that the returned `Stream[R]` is correct at that call site — it's asserted, not derived, so a mistake in the cast itself (e.g. casting to the wrong `R`) wouldn't be caught. → **Mitigation:** the cast is trivially correct by construction (`R` is exactly the mapper's own declared return type), and it's the only cast introduced by this change — scoped to two call sites, not spread through the codebase.
- **[Risk]** A caller who does `s: Stream[int] = Stream.of([1,2,3]); s.map(str)` and then keeps using `s` (rather than the fluent return value) expecting `Stream[int]` will get stale/wrong static types for `s`, even though `s.map(str)`'s *return value* correctly types as `Stream[str]`. This is inherent to typing a mutating builder and can't be fully closed without the immutable-pipeline redesign. → **Mitigation:** none within this change's scope; documented here so it's a known, intentional limitation rather than a surprise. Existing code always uses the fluent chained-return style already (`CLAUDE.md`, README examples), so this edge case has low real-world exposure.
- **[Risk]** Making `T` a free (unbounded) `TypeVar` on `Stream` means `distinct()` still type-checks for non-hashable `T` even though it fails at runtime (`set.add()` raises `TypeError`). → **Mitigation:** out of scope (see Open Questions); pre-existing gap, not introduced or worsened by this change.

## Migration Plan

Purely additive/typing-only — no runtime code paths change, so no rollout or rollback concerns beyond normal review. `ty` may newly report errors in any *downstream* code (outside `src/snakestream`, if any exists in this repo) that relied on the previously-`Unknown` element type; none expected within this repo's own test suite since tests don't do static type assertions, but worth confirming `ty` is clean on `tests/` too if it's in scope for the checker.

## Open Questions

- Should `T` gain a `Hashable` bound (or `distinct()` be typed with a separate bounded `TypeVar`) to catch non-hashable-element `distinct()` misuse statically? Deferred — would need its own design pass on how it interacts with every other op that doesn't need hashability, and isn't part of the gap this change targets.
