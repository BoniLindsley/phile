# Standard libraries.
import collections.abc as _collections_abc
import typing as _typing

_T = _typing.TypeVar('_T')


class DelayedQueue(_typing.Generic[_T]):
    delay_sec: float = ...

    def __init__(self, delay: float) -> None:
        ...

    def put(self, element: _T, delay: bool = ...) -> None:
        ...

    def close(self) -> None:
        ...

    def get(self) -> _typing.Optional[_T]:
        ...

    def remove(
        self, predicate: _collections_abc.Callable[[_T], bool]
    ) -> _typing.Optional[_T]:
        ...
