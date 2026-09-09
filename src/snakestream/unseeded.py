from __future__ import annotations

from typing import Any

# Sentinel for "no value yet": distinguishes an unseeded reduction/accumulation
# from one seeded with a legitimately falsy identity. Lives here rather than in
# terminals.py or collectors.py because both need it and neither is downstream
# of the other, so neither is a plausible host.
UNSET = object()


def unseeded(container: Any) -> Any:
    """The rule stated once: an accumulation that never saw an element
    finishes as None. A function rather than five inlined comparisons because
    it is the only mechanism that reaches both terminals.py's sinks (through
    its _UnseededSink) and collectors.py's closures, which are dataclass
    boxes rather than sinks and so cannot share a base class with them - see
    design Decision 3 of collapse-unseeded-accumulation-rule."""
    return None if container is UNSET else container
