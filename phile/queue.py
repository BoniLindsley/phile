#!/usr/bin/env python3
"""
-------------------------------------
Extension to standard library `queue`
-------------------------------------
"""

# Standard library.
import queue
import typing

_T = typing.TypeVar("_T")


class IterableSimpleQueue(queue.SimpleQueue[_T]):

    __Self = typing.TypeVar("__Self", bound="IterableSimpleQueue[_T]")

    def __iter__(self: __Self) -> __Self:
        return self

    def __next__(self) -> _T:
        try:
            return self.get_nowait()
        except queue.Empty as error:
            raise StopIteration from error
