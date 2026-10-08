+++
id = "type-checking-import"
title = "Fixed an unqualified `TYPE_CHECKING`-only import"
filed = 2026-08-03
closed = 2026-08-03
outcome = "shipped"
+++

The `TYPE_CHECKING`-only import in `stream.py:17` used an unqualified
`from stream_builder import StreamBuilder`, which would fail if ever
actually evaluated. Fixed to `from snakestream.stream_builder import
StreamBuilder`.
