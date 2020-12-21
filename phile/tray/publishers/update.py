#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import datetime
import types
import typing


class Target(typing.Protocol):

    def __enter__(
        self
    ) -> typing.Callable[[], datetime.timedelta]:  # pragma: no cover
        ...

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:  # pragma: no cover
        ...


class SelfTarget(Target):

    def __call__(self) -> datetime.timedelta:
        raise NotImplementedError()

    def __enter__(self) -> typing.Callable[[], datetime.timedelta]:
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self.on_exit()
        return None

    def on_exit(self) -> None:
        raise NotImplementedError()


async def sleep_loop(target: Target) -> None:
    with target as update:
        while True:
            await asyncio.sleep(update().total_seconds())
