from snakestream.comparator import KeyComparator, comparing, nulls_first, nulls_last
from snakestream.type import Comparator


def compare(a: int, b: int) -> int:
    return a - b


key_comparator_in: KeyComparator = nulls_first(comparing(lambda x: x))
key_comparator_chained: KeyComparator = key_comparator_in.then_comparing(lambda x: x)

bare_comparator_out: Comparator[int] = nulls_last(compare)

default_is_a_key_comparator: KeyComparator = nulls_first()

reversed_stays_a_key_comparator: KeyComparator = nulls_last(comparing(lambda x: x)).reversed()
