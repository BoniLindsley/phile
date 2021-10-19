#!/usr/bin/env python3
"""
.. automodule:: phile.asyncio.pubsub

---------------------------------------
Extra :mod:`asyncio`-related operations
---------------------------------------
"""

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import contextvars
import datetime
import functools
import logging
import queue
import socket
import threading
import typing

_T = typing.TypeVar("_T")
_T_co = typing.TypeVar("_T_co", covariant=True)

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)

wait_for_timeout: contextvars.ContextVar[
    datetime.timedelta
] = contextvars.ContextVar(
    "wait_for_timeout", default=datetime.timedelta(seconds=2)
)
"""Default timeout value for :func:`wait_for`."""


async def noop() -> None:
    pass


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
    target: asyncio.Future[_T],
) -> typing.Optional[_T]:
    target.cancel()
    try:
        return await target
    except asyncio.CancelledError:
        if not target.cancelled():
            raise
    return None


def cancel(
    tasks_to_cancel: collections.abc.Iterable[asyncio.Task[typing.Any]],
) -> None:
    loop = asyncio.get_event_loop()
    gatherer = asyncio.gather(*tasks_to_cancel, return_exceptions=True)
    gatherer.cancel()
    try:
        loop.run_until_complete(gatherer)
    except asyncio.CancelledError:
        pass


def handle_exceptions(
    done_tasks: collections.abc.Iterable[asyncio.Task[typing.Any]],
) -> None:
    loop = asyncio.get_event_loop()
    possible_exceptions = (
        task.exception() for task in done_tasks if not task.cancelled()
    )
    raised_exceptions = (
        exception
        for exception in possible_exceptions
        if exception is not None
    )
    handle_exception = loop.call_exception_handler
    for exception in raised_exceptions:
        handle_exception(
            {
                "message": "Unhandled exception during loop shutdown.",
                "exception": exception,
            }
        )


def close() -> None:
    loop = asyncio.get_event_loop()
    try:
        try:
            _logger.debug("Cancelling existing asyncio tasks.")
            pending_tasks = asyncio.all_tasks(loop)
            if pending_tasks:
                cancel(pending_tasks)
                handle_exceptions(pending_tasks)
            del pending_tasks
        finally:
            _logger.debug("Shutting down asyncio loop states.")
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
    finally:
        try:
            asyncio.set_event_loop(None)
        finally:
            loop.close()


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
        self.__raised_exception: BaseException

    def run(self) -> None:
        try:
            super().run()
        # Propagating all exceptions into asyncio loop.
        except BaseException as error:  # pylint: disable=broad-except
            self.__raised_exception = error
        self.__running_loop.call_soon_threadsafe(self.__stopped.set)

    async def async_join(self) -> None:
        await self.__stopped.wait()
        with contextlib.suppress(AttributeError):
            raise self.__raised_exception


class QueueClosed(Exception):
    pass


# Pylint does not think it is a type anymore when [_T] is appended.
class Queue(asyncio.Queue[_T]):  # pylint: disable=inherit-non-class
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self._closed = asyncio.Event()

    def close(self) -> None:
        self._closed.set()

    async def get(self) -> _T:
        try:
            return self.get_nowait()
        except asyncio.QueueEmpty:
            pass
        close_checker = asyncio.create_task(self._closed.wait())
        getter = asyncio.create_task(super().get())
        tasks_to_wait_for: set[asyncio.Task[typing.Any]] = {
            close_checker,
            getter,
        }
        try:
            done, _pending = await asyncio.wait(
                tasks_to_wait_for,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in tasks_to_wait_for:
                await cancel_and_wait(task)
        if getter in done:
            return await getter
        raise QueueClosed()

    def get_nowait(self) -> _T:
        try:
            return super().get_nowait()
        except asyncio.QueueEmpty as error:
            if self._closed.is_set():
                raise QueueClosed() from error
            raise

    async def put(self, item: _T) -> None:
        if self._closed.is_set():
            raise QueueClosed("Cannot put items into a closed queue.")
        await super().put(item)

    def put_nowait(self, item: _T) -> None:
        if self._closed.is_set():
            raise QueueClosed("Cannot put items into a closed queue.")
        super().put_nowait(item)


class ThreadedTextIOBase:
    # Only implementing readline as reading line by line
    # is the only reliable platform-independent read operation on stdin.

    def __init__(
        self,
        parent_stream: typing.IO[str],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._buffered_lines: Queue[str] = Queue()
        self._loop = asyncio.get_event_loop()
        self._parent_stream = parent_stream
        self._request_queue: queue.SimpleQueue[
            bool
        ] = queue.SimpleQueue()
        self._worker_thread = Thread(target=self._run, daemon=True)
        self._worker_thread.start()

    def close(self) -> None:
        # Does not deterministically close the stream.
        # The worker thread is likely to be stuck waiting for a new line.
        # But this stops it from reading again if that ever returns.
        self._request_queue.put_nowait(False)
        # Try to return from all readline calls.
        self._loop.call_soon_threadsafe(self._buffered_lines.close)

    async def readline(self) -> str:
        try:
            try:
                return self._buffered_lines.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._request_queue.put_nowait(True)
            return await self._buffered_lines.get()
        except QueueClosed as error:
            raise ValueError("No more data available.") from error

    def _run(self) -> None:
        try:
            while self._request_queue.get():
                next_line = self._parent_stream.readline()
                # Intention catch to propagate exception.
                # pylint: disable=broad-except
                if not next_line:
                    break
                self._loop.call_soon_threadsafe(
                    self._buffered_lines.put_nowait, next_line
                )
        finally:
            self._parent_stream.close()
            self._loop.call_soon_threadsafe(self._buffered_lines.close)
