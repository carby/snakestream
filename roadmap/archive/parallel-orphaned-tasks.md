+++
id = "parallel-orphaned-tasks"
title = "`parallel()` no longer leaves orphaned `asyncio` tasks"
filed = 2026-08-03
closed = 2026-08-03
outcome = "shipped"
+++

`parallel()` pipelines left orphaned `asyncio` tasks (and "Task exception
was never retrieved" warnings) when one branch raised mid-stream. Fixed in
`ParallelStream._parallel` by cancelling and draining remaining tasks in a
`finally` block.
