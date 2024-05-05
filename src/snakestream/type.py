import abc
from typing import Any, AsyncGenerator, AsyncIterable, Awaitable, Callable, Generator, Iterable, Optional, TypeVar, Union, List


#
# Generic types
#
T = TypeVar('T')
R = TypeVar('R')

Predicate = Callable[[T], Union[bool, Awaitable[bool]]]

# Intermediaries
Filterer = Callable[[T], T]
Mapper = Callable[[T], Optional[R]]
FlatMapper = Callable[[Union[Iterable, AsyncIterable, Generator, AsyncGenerator]], 'AbstractStream']
Comparator = Callable[[T, T], Union[bool, Awaitable[bool]]]
Consumer = Callable[[T], T]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, Union[T, R]], Union[T, R]]


#
# Classes
#
class AbstractStream(metaclass=abc.ABCMeta):

    @staticmethod
    @abc.abstractclassmethod
    def of(source: Any) -> 'AbstractStream':
        raise NotImplementedError

    @staticmethod
    @abc.abstractclassmethod
    def empty() -> 'AbstractStream':
        raise NotImplementedError

    @staticmethod
    @abc.abstractclassmethod
    async def concat(a: 'AbstractStream', b: 'AbstractStream') -> 'AbstractStream':
        raise NotImplementedError

    @staticmethod
    @abc.abstractclassmethod
    def builder() -> 'AbstractStreamBuilder':
        raise NotImplementedError

    # Intermediaries
    @abc.abstractclassmethod
    def filter(self, predicate: Predicate) -> 'AbstractStream':
        raise NotImplementedError

    @abc.abstractclassmethod
    def map(self, mapper: Mapper) -> 'AbstractStream':
        raise NotImplementedError

    @abc.abstractclassmethod
    def flat_map(self, flat_mapper: FlatMapper) -> 'AbstractStream':
        raise NotImplementedError

    @abc.abstractclassmethod
    def sorted(self, comparator: Optional[Comparator] = None, reverse=False) -> 'AbstractStream':
        raise NotImplementedError

    @abc.abstractclassmethod
    def distinct(self) -> 'AbstractStream':
        raise NotImplementedError

    @abc.abstractclassmethod
    def peek(self, consumer: Consumer) -> 'AbstractStream':
        raise NotImplementedError

    # Terminals
    @abc.abstractclassmethod
    def collect(self, collector: Callable) -> Union[AsyncGenerator, List]:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def reduce(self, identity: Union[T, R], accumulator: Accumulator) -> Union[T, R]:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def for_each(self, consumer: Callable[[T], Any]) -> None:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def find_any(self) -> Optional[Any]:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def max(self, comparator: Comparator) -> Optional[T]:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def min(self, comparator: Comparator) -> Optional[T]:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def all_match(self, predicate: Predicate) -> bool:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def none_match(self, predicate: Predicate) -> bool:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def any_match(self, predicate: Predicate) -> bool:
        raise NotImplementedError

    @abc.abstractclassmethod
    async def count(self) -> int:
        raise NotImplementedError


class AbstractStreamBuilder(metaclass=abc.ABCMeta):

    @abc.abstractclassmethod
    def add(self, element: T) -> 'AbstractStreamBuilder':
        raise NotImplementedError

    @abc.abstractclassmethod
    def accept(self, element: T) -> None:
        raise NotImplementedError

    @abc.abstractclassmethod
    def build(self) -> 'AbstractStream':
        raise NotImplementedError
