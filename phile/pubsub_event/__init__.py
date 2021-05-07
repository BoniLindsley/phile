#!/usr/bin/env python3
"""
--------------------
For event processing
--------------------
"""

# Standard libraries.
import asyncio
import typing

_T = typing.TypeVar('_T')

_Node = asyncio.Future[tuple[_T, asyncio.Future[typing.Any]]]


class NoMoreMessages(Exception):
    pass


class Publisher(typing.Generic[_T]):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._next_message: _Node[_T] = (
            asyncio.get_event_loop().create_future()
        )

    def push(self, message: _T) -> None:
        pushed_node = self._next_message
        self._next_message = next_message = (
            asyncio.get_event_loop().create_future()
        )
        pushed_node.set_result((message, next_message))

    def stop(self) -> None:
        self._next_message.cancel()


class Subscriber(typing.Generic[_T]):

    def __init__(
        self,
        *args: typing.Any,
        publisher: Publisher[_T],
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._next_message: _Node[_T] = publisher._next_message

    async def pull(self) -> _T:
        try:
            current_message = self._next_message
            message, self._next_message = (
                await asyncio.shield(current_message)
            )
        except asyncio.CancelledError as error:
            if current_message.cancelled():
                raise NoMoreMessages() from error
            raise
        return message
