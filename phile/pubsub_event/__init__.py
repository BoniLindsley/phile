#!/usr/bin/env python3
"""
--------------------
For event processing
--------------------
"""

# Standard libraries.
import asyncio
import dataclasses
import typing

_T = typing.TypeVar('_T')


class Node(typing.Generic[_T]):

    class EndReached(RuntimeError):
        pass

    def __init__(
        self,
        *args: typing.Any,
        content: typing.Optional[_T] = None,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.content = content
        self._next_node: typing.Optional['Node[_T]'] = None
        self._next_available = asyncio.Event()

    async def next(self) -> 'Node[_T]':
        await self._next_available.wait()
        next_node = self._next_node
        if next_node is None:
            raise self.EndReached()
        return next_node

    def set_next(self, content: _T) -> 'Node[_T]':
        assert not self._next_available.is_set()
        self._next_node = next_node = Node(content=content)
        self._next_available.set()
        return next_node

    def set_to_end(self) -> None:
        assert not self._next_available.is_set()
        self._next_available.set()


class NoMoreEvents(Exception):
    pass


class Publisher(typing.Generic[_T]):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._prev_node = Node[_T]()

    def push(self, message: _T) -> None:
        self._prev_node = self._prev_node.set_next(content=message)

    def stop(self) -> None:
        self._prev_node.set_to_end()


class Subscriber(typing.Generic[_T]):

    def __init__(
        self,
        *args: typing.Any,
        publisher: Publisher[_T],
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._prev_node = publisher._prev_node

    async def pull(self) -> _T:
        try:
            self._prev_node = current_node = await self._prev_node.next()
        except Node.EndReached as error:
            raise NoMoreEvents() from error
        return typing.cast(_T, current_node.content)
