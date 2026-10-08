+++
id = "exception-group-in-close"
title = "`ExceptionGroup` in `Stream.close()` is declined"
filed = 2026-08-28
closed = 2026-08-28
outcome = "declined"
+++

**`ExceptionGroup` in `Stream.close()` is declined** (2026-08-28),
resolving **Now** open question 2 after three batches of deferral — as a
decision this time, not a fourth park. No code changed; the rationale is now
written into the `stream-close-handling` spec, beside the rule it explains,
which is what stops the question being re-asked.

The objection recorded on 2026-08-18 was only ever "the CI matrix still
targets Python 3.10", which needs a `sys.version_info >= (3, 11)` fork —
an objection with an expiry date, and it has now expired: 3.10 left the
matrix in `raise-python-floor-to-311` (2026-09-04). That is not why the
answer is no. Java's `AbstractPipeline.close()`
composes handlers through `Streams.composeWithExceptions()`: it runs every
handler, calls `addSuppressed()` on the first exception for each later one,
and rethrows *the first*. Java never throws a composite here. So
first-exception-wins-with-the-rest-attached is the contract, and `add_note()`
is its faithful Python spelling rather than a compromise forced by the
version floor. An `ExceptionGroup` changes which type escapes `close()` —
`except ValueError` around a `close()` silently stops matching — which is a
divergence in *observable API behaviour*, the one category the guiding
principle calls a defect.

The case against, kept because it is not weak: PEP 654's own motivating
example is multiple failures during cleanup, and a caller of an async-first
library already handles `ExceptionGroup` from `asyncio.TaskGroup` and
already writes `except*`. It loses on cost/benefit rather than on principle
— two or more close handlers that both raise is the rare branch of a rare
branch, programmatic catchability of the *second* failure buys nearly
nothing over a note in the traceback, and the type change is paid by every
caller. The `exceptiongroup` backport would remove the version fork at the
price of this library's first runtime dependency, for its rarest code path;
ruled out on sight.

Nothing was touched but the spec: `stream.py`'s `close()`, both multi-raise
tests, and the `noqa: PERF203` (whose stated reason — the run-every-handler
contract — is unaffected either way) all stand unchanged.
