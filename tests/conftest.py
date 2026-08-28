"""
Dummy conftest.py for snakestream.

If you don't know what this is for, just leave it empty.
Read more about conftest.py under:
- https://docs.pytest.org/en/stable/fixture.html
- https://docs.pytest.org/en/stable/writing_plugins.html
"""

import asyncio
import sys

import pytest
import pytest_asyncio

sys.path.append("src")


class MyObject:
    def __init__(self, identifier, name):
        self.id = identifier
        self.name = name

    def __eq__(self, other):
        if isinstance(other, MyObject):
            return self.id == other.id and self.name == other.name
        return False

    def __hash__(self):
        return hash((self.id, self.name))


@pytest.fixture
def int_2_letter():
    return {
        1: "a",
        2: "b",
        3: "c",
        4: "d",
        5: "e",
    }


@pytest.fixture
def letter_2_int(int_2_letter):
    return {v: k for k, v in int_2_letter.items()}


@pytest_asyncio.fixture(scope="function")
async def async_int_to_letter(int_2_letter):
    async def inner(x: int) -> str:
        await asyncio.sleep(0.01)
        return int_2_letter[x]

    return inner


# --- the tie-break setup shared by test_max/test_min/test_max_by/test_min_by ---
#
# comparator-contract requires the first of tied elements in *encounter* order,
# and is_new_extremum() delivers that by keeping the element it saw first - so
# on an ordered pipeline the delivery barrier is what makes "first seen" and
# "first in encounter order" the same thing. These four files all need the same
# source to show it, hence conftest rather than four copies.
#
# One slow element at position 0, everything else cheap. Not the slow *head* of
# tests/test_racing_encounter_order.py: with PROCESSES branches, a slow head is
# pulled by all of them at t=0 and still finishes before the tail, so it puts no
# reordering pressure on element 0 specifically. With a single slow element the
# whole tail - TIED_LATE included - drains past it while it is still sleeping,
# so under a plain race the later of the two tied records is seen first and only
# the barrier makes the earlier one win.

TIED_EARLY = ("early", 5)
TIED_LATE = ("late", 5)
TIE_SOURCE = [
    TIED_EARLY,
    ("b", 1),
    ("c", 2),
    ("d", 3),
    ("e", 1),
    ("f", 2),
    ("g", 3),
    ("h", 1),
    ("i", 2),
    ("j", 3),
    TIED_LATE,
    ("l", 1),
]


def by_key(x, y):
    """A comparator that ties TIED_EARLY with TIED_LATE - a partial key over
    distinguishable records, which is the only shape the tie-break is
    observable in."""
    return x[1] - y[1]


async def overtaken(pair):
    """Slow for TIED_EARLY alone, so every later element overtakes it."""
    await asyncio.sleep(0.2 if pair is TIED_EARLY else 0.001)
    return pair
