+++
id = "to-generator-as-a-factory"
title = "`to_generator` is deleted, not made a factory"
filed = 2026-09-09
closed = 2026-09-10
outcome = "shipped"
shipped_as = "remove-to-generator"
+++

**`to_generator` is deleted, not made a factory** (closed 2026-09-10; filed
2026-09-09). Shipped as `remove-to-generator`.

The item was filed against a real asymmetry — every collector factory in
`collectors.py` is called (`collect(to_list())`), while `to_generator` is a
bare `StreamingCollector` instance in `collector.py`, so the call site is
`collect(to_generator)`, no parens. Its proposed fix was to make
`to_generator` a factory too, buying call-site symmetry.

That fix was superseded and inverted before implementation. There were two
asymmetries, not one: the parens are the harmless one, raising immediately
when gotten wrong; the return contract is the invisible, harmful one —
`collect(to_generator)` returns an `AsyncGenerator` to iterate, not
something to `await`, unlike every other `collect()` argument. Making the
call site `collect(to_generator())` would have fixed only the first and
removed the one visual cue the second ever existed, since it would then
look identical to `collect(to_list())` while still behaving differently.
The item's own summary — "this buys exactly one thing, call-site symmetry"
— was the tell: it named the cosmetic asymmetry and missed the real one.

`remove-to-generator` deleted `to_generator` and `StreamingCollector`
outright instead. `collect()` now accepts only a `Collector`; every call
site migrated to `iterator()`, which `to_generator` was a slower second
spelling of — it composed through the same element-producing operation and
only re-yielded what `iterator()` already produced, at +31% per element on
a 200k-element `.map()` pipeline (measured 878 vs 1146 ns/element). See
`remove-to-generator/design.md` Decision 1 for the full argument.

The item's own reasoning was wrong a second time, on a smaller point: it
claimed the factory fix "does not buy less surface on `maybe_aclosing`" and
that deletion bought no less. False for deletion — `collector.py`'s import
of `maybe_aclosing` was that name's last cross-module caller, so removing
it left `maybe_aclosing` used only inside `execution.py`. CLAUDE.md's
naming rule ("a leading underscore iff no other module uses it") made that
a rename, not an option: `maybe_aclosing` -> `_maybe_aclosing`, caught by
independent peer review after the change's own tasks had already landed,
and folded into the same commit that closed this item.
