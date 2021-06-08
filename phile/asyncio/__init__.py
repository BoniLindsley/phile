#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import contextvars
import datetime
import functools
import queue
import socket
import threading
import typing

_T = typing.TypeVar('_T')
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


async def cancel_and_wait(
    target: asyncio.Future[_T]
) -> typing.Optional[_T]:
    target.cancel()
    try:
        return await target
    except asyncio.CancelledError:
        if not target.cancelled():
            raise
    return None


# TODO[python/mypy#9922]: Use `asyncio.Task[_T_co]` in return value.
@contextlib.asynccontextmanager
async def open_task(
    awaitable: collections.abc.Awaitable[_T_co],
    *args: typing.Any,
    suppress_cancelled_error_if_not_done: bool = False,
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
        try:
            await task
        except asyncio.CancelledError:
            if not suppress_cancelled_error_if_not_done:
                raise


async def close_subprocess(
    # TODO[Pylint issue 1469]: Does not recognize `asyncio.subprocess`.
    subprocess: asyncio.subprocess.Process,  # pylint: disable=no-member
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
    readable_future = asyncio.get_running_loop().create_future()
    with open_reader(
        file_descriptor,
        functools.partial(readable_future.set_result, None),
    ):
        await readable_future
    return True


class Thread(threading.Thread):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.__running_loop = asyncio.get_running_loop()
        self.__stopped = asyncio.Event()

    def run(self) -> None:
        super().run()
        self.__running_loop.call_soon_threadsafe(self.__stopped.set)

    async def async_join(self) -> None:
        await self.__stopped.wait()


class ThreadedTextIOBase:

    def __init__(
        self,
        parent_stream: typing.IO[str],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._io_thread = threading.Thread(target=self._run, daemon=True)
        self._loop = asyncio.get_event_loop()
        self._parent_stream = parent_stream
        self._request_queue = queue.SimpleQueue[asyncio.Future[str]]()
        self._io_thread.start()

    async def readline(self) -> str:
        next_line_future = asyncio.Future[str]()
        self._request_queue.put(next_line_future)
        next_line = await next_line_future
        return next_line

    def _run(self) -> None:
        while True:
            next_line_future = self._request_queue.get()
            try:
                next_line = self._parent_stream.readline()
            # Intention catch to propagate exception.
            # pylint: disable=broad-except
            except BaseException as exception:
                self._loop.call_soon_threadsafe(
                    next_line_future.set_exception, exception
                )
                return
            self._loop.call_soon_threadsafe(
                next_line_future.set_result, next_line
            )
