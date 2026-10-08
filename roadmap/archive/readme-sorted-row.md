+++
id = "readme-sorted-row"
title = "Added `sorted()`'s row to README's Stream API table"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Added `sorted()`'s row to README's Stream API table. `sorted()` had been
implemented since before this roadmap existed (`stream.py:191`) but was
never given a row in the table; the migration log referenced it three
times, which is what made the omission easy to miss. Doc-only, no code
change.
