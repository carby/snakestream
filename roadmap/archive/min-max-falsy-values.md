+++
id = "min-max-falsy-values"
title = "`min()`/`max()` no longer skip falsy values"
filed = 2026-08-03
closed = 2026-08-03
outcome = "shipped"
+++

`min()`/`max()` used to silently skip falsy candidate values (`0`, `""`,
`False`) because of a truthiness check in `Stream._min_max`. Fixed by
replacing the `None`-as-sentinel logic with a proper `_UNSET` sentinel.
