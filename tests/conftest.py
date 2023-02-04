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
        1: 'a',
        2: 'b',
        3: 'c',
        4: 'd',
        5: 'e',
    }


@pytest.fixture
def letter_2_int(int_2_letter):
    return {v: k for k, v in int_2_letter.items()}


@pytest.fixture(scope='function')
async def async_int_to_letter(int_2_letter):
    async def inner(x: int) -> str:
        await asyncio.sleep(0.01)
        return int_2_letter[x]
    return inner
