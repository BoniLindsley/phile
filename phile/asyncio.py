#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import contextvars
import datetime
import socket
import typing

_T_co = typing.TypeVar('_T_co', covariant=True)

wait_for_timeout: contextvars.ContextVar[datetime.timedelta] = (
    contextvars.ContextVar(
        'wait_for_timeout', default=datetime.timedelta(seconds=2)
    )
)
"""Default timeout value for :func:`wait_for`."""


async def wait_for(
    awaitable: typing.Awaitable[_T_co],
    timeout: typing.Optional[datetime.timedelta] = None,
) -> _T_co:
    """Same as :func:`~asyncio.wait_for` with a default timeout."""
    if timeout is None:
        timeout = wait_for_timeout.get()
    return await asyncio.wait_for(
        awaitable, timeout=timeout.total_seconds()
    )


# TODO[python/mypy#9922]: Use `asyncio.Task[_T_co]` in return value.
@contextlib.asynccontextmanager
async def open_task(
    awaitable: collections.abc.Awaitable[_T_co],
    *args: typing.Any,
    **kwargs: typing.Any,
) -> collections.abc.AsyncIterator[asyncio.Task[typing.Any]]:
    if isinstance(awaitable, asyncio.Task):
        task = awaitable
        assert not args
        assert not kwargs
    else:
        task = asyncio.create_task(awaitable, *args, **kwargs)
    try:
        yield task
    finally:
        task.cancel()


async def close_subprocess(
    subprocess: asyncio.subprocess.Process
) -> None:
    """Ensure the given subprocess is terminated."""
    # We do not know what state the process is in.
    # We assume the user had already exhausted
    # all nice ways to terminate it.
    # So just kill it.
    with contextlib.suppress(ProcessLookupError):
        subprocess.kill()
    # Killing just sends the request / signal.
    # Wait to make sure it is actually terminated.
    # And automatically-created pipes and inherited fds,
    # such as any given in stdin, stdout, stderr,
    # are closed after termination.
    await subprocess.communicate()


@contextlib.contextmanager
def open_reader(
    file_descriptor: typing.Union[int, socket.socket],
    callback: collections.abc.Callable[[], typing.Any],
) -> collections.abc.Iterator[None]:
    running_loop = asyncio.get_running_loop()
    try:
        running_loop.add_reader(file_descriptor, callback)
        yield
    finally:
        running_loop.remove_reader(file_descriptor)


async def readable(
    file_descriptor: typing.Union[int, socket.socket]
) -> typing.Literal[True]:
    readable = asyncio.Event()
    with open_reader(file_descriptor, readable.set):
        await readable.wait()
    return True
