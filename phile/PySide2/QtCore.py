#!/usr/bin/env python3
"""
-------------------------------
Extending :mod:`PySide2.QtCore`
-------------------------------
"""

# Standard library.
import collections.abc
import concurrent.futures
import contextvars
import datetime
import functools
import threading
import typing

# External dependencies.
import PySide2.QtCore

_T = typing.TypeVar('_T')

wait_for_timeout: contextvars.ContextVar[datetime.timedelta] = (
    contextvars.ContextVar(
        'wait_for_timeout', default=datetime.timedelta(seconds=2)
    )
)
"""Default timeout value when processing PySide2 events."""


def process_deferred_delete_events() -> None:
    # Calling `processEvents` does not process `DeferredDelete` events.
    # Asking `sendPostedEvents` to process all events
    # (which is done by`processEvents`, I think)
    # also does not process it.
    # So this needs to be explicitly called.
    PySide2.QtCore.QCoreApplication.sendPostedEvents(
        None, PySide2.QtCore.QEvent.DeferredDelete
    )


def process_events() -> None:
    PySide2.QtCore.QCoreApplication.processEvents(
        PySide2.QtCore.QEventLoop.AllEvents,
        int(wait_for_timeout.get() / datetime.timedelta(milliseconds=1))
    )


class CallRequest(PySide2.QtCore.QEvent):

    event_type = PySide2.QtCore.QEvent.Type(  # type: ignore[call-arg]
        PySide2.QtCore.QEvent.registerEventType()
    )

    def __init__(
        self, callback: typing.Callable[[], typing.Any]
    ) -> None:
        """
        :param callback:
            Callable to eventually call in the Qt event loop
            whenever ``self`` is.
        :type callback: typing.Callable[[], typing.Any]
        """
        super().__init__(self.event_type)
        self.callback = callback


class Caller(PySide2.QtCore.QObject):

    def customEvent(
        self, event_to_handle: PySide2.QtCore.QEvent
    ) -> None:
        """Internal."""
        if event_to_handle.type() == CallRequest.event_type:
            try:
                event_to_handle.callback()
            finally:
                self.deleteLater()
        else:
            super().customEvent(event_to_handle)


def call_soon_threadsafe(
    callback: typing.Callable[..., typing.Any],
    *args: typing.Any,
    thread: typing.Optional[PySide2.QtCore.QThread] = None,
) -> None:
    """Schedule ``callback`` to be called in the Qt event loop."""
    if args:
        callback = functools.partial(callback, *args)
    if thread is None:
        thread = PySide2.QtCore.QCoreApplication.instance().thread()
    event_to_post = CallRequest(callback=callback)
    caller = Caller()
    try:
        caller.moveToThread(thread)
        caller.setParent(thread)
        PySide2.QtCore.QCoreApplication.postEvent(caller, event_to_post)
    except:
        caller.deleteLater()
        raise


class Future(concurrent.futures.Future[_T]):
    """Fixes typing of add_done_callback."""

    __Self_contra = typing.TypeVar(
        '__Self_contra', bound='Future[_T]', contravariant=True
    )

    # The name is used by superclass. Keeping it for consistency.
    def add_done_callback(  # pylint: disable=invalid-name
        self: __Self_contra,
        fn: collections.abc.Callable[[__Self_contra], typing.Any]
    ) -> None:
        super().add_done_callback(
            typing.cast(
                collections.abc.Callable[
                    [concurrent.futures.Future[typing.Any]], typing.Any],
                fn,
            )
        )


class Task(Future[_T]):

    def __init__(
        self,
        *args: typing.Any,
        callback: collections.abc.Callable[[], _T],
        **kwargs: typing.Any,
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._callback = callback

    def run(self) -> None:
        if not self.set_running_or_notify_cancel():
            return
        try:
            result = self._callback()
        # Intentionally catching all exception to propagate.
        # pylint: disable=broad-except
        except BaseException as exception:
            self.set_exception(exception)
        else:
            self.set_result(result)


class Executor(concurrent.futures.Executor):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.futures = set[Task[typing.Any]]()
        self.future_done_event = threading.Event()
        self.is_shutdown = False
        self.shutdown_lock = threading.Lock()

    def submit(
        self,
        fn: collections.abc.Callable[..., _T],
        /,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> concurrent.futures.Future[_T]:
        callback: collections.abc.Callable[[], _T]
        if args or kwargs:
            callback = functools.partial(
                fn,
                *args,
                **kwargs,
            )
        else:
            callback = fn
        task = Task[_T](callback=callback)
        task.add_done_callback(self.futures.discard)
        task.add_done_callback(
            lambda _future: self.future_done_event.set()
        )
        with self.shutdown_lock:
            if self.is_shutdown:
                raise RuntimeError('Executor is shut down.')
            call_soon_threadsafe(callback=task.run)
            self.futures.add(task)
        return task

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False
    ) -> None:
        with self.shutdown_lock:
            self.is_shutdown = True
        if cancel_futures:
            for future in self.futures.copy():
                future.cancel()
        if wait:
            while self.futures:
                self.future_done_event.wait()
                self.future_done_event.clear()
        super().shutdown(wait=wait, cancel_futures=cancel_futures)
