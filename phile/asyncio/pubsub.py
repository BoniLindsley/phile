#!/usr/bin/env python3

# Standard libraries.
import asyncio
import typing

_T = typing.TypeVar('_T')


class Node(typing.Generic[_T]):

    class AlreadySet(Exception):
        pass

    class EndReached(Exception):
        pass

    class NotSet(Exception):
        pass

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._value: _T
        """Assigned when the node is set, and not set as an end."""
        self._value_set = asyncio.Event()
        """Set when the node is set."""
        self.next_node: Node[_T]
        """Assigned when the node is set, and not set as an end."""

    async def get(self) -> _T:
        await self._value_set.wait()
        return self.get_nowait()

    def get_nowait(self) -> _T:
        try:
            return self._value
        except AttributeError as error:
            if self._value_set.is_set():
                raise self.EndReached() from error
            raise self.NotSet() from error

    def is_end(self) -> bool:
        return not hasattr(self, '_value') and self._value_set.is_set()

    def set(self, new_value: _T) -> None:
        if self._value_set.is_set():
            raise self.AlreadySet()
        # Creating an instance creates an event
        # which requires a current loop.
        # If one is not set, it may throw.
        # So create one first to check for one, in case it raises.
        self.next_node = type(self)()
        self._value_set.set()
        self._value = new_value

    def set_end(self) -> None:
        if self._value_set.is_set():
            raise self.AlreadySet()
        self._value_set.set()


class View(typing.Generic[_T]):

    def __init__(
        self,
        *args: typing.Any,
        next_node: Node[_T],
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._next_node = next_node

    def __aiter__(self) -> 'View[_T]':
        return self

    async def __anext__(self) -> _T:
        try:
            return await self.get()
        except Node.EndReached as error:
            raise StopAsyncIteration() from error

    async def get(self) -> _T:
        current_node = self._next_node
        next_value = await self._next_node.get()
        self._next_node = current_node.next_node
        return next_value


class Queue(typing.Generic[_T]):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._next_node = Node[_T]()

    def __aiter__(self) -> View[_T]:
        return View[_T](next_node=self._next_node)

    async def get(self) -> _T:
        return await self._next_node.get()

    def put(self, value: _T) -> None:
        current_node = self._next_node
        current_node.set(value)
        self._next_node = current_node.next_node

    def put_done(self) -> None:
        self._next_node.set_end()
