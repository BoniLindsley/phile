#!/usr/bin/env python3

# Emitter classes are wrapped in a function
# so that imports are only done when the respective observers are used.
# pylint: disable=import-outside-toplevel

# The functions do not conform to snake case for easier naming.
# pylint: disable=invalid-name

# Side effect is shadowing of module scope names.
# pylint: disable=redefined-outer-name

# Mimicking arguments of watchdog observer but allowing for subclassing.
# pylint: disable=keyword-arg-before-vararg
"""
------------------------------------------
Mixing :mod:`watchdog` with :mod:`asyncio`
------------------------------------------
"""

# Standard library.
import asyncio
import collections
import collections.abc
import contextlib
import platform
import typing
import warnings

# External dependencies.
import watchdog.events
import watchdog.observers
import watchdog.observers.api
import watchdog.utils

# Internal modules.
import phile.asyncio
import phile.pubsub_event


class EventQueue(
    phile.pubsub_event.Publisher[watchdog.events.FileSystemEvent]
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self._loop = asyncio.get_event_loop()

    def put(
        self,
        event_data: tuple[watchdog.events.FileSystemEvent,
                          watchdog.observers.api.ObservedWatch],
    ) -> None:
        """Thread-safe push. Named so to satisfy EventEmitter usage."""
        self._loop.call_soon_threadsafe(self.push, event_data[0])


class EventEmitter(
    phile.asyncio.Thread,
    watchdog.observers.api.EventEmitter,
):
    pass


class BaseObserver:
    """Base observer."""

    def __init__(
        self,
        emitter_class: collections.abc.Callable[[
            watchdog.observers.api.EventQueue,
            watchdog.observers.api.ObservedWatch,
            float,
        ], EventEmitter],
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.timeout = timeout
        self._emitter_class = emitter_class
        self._emitters: (
            dict[watchdog.observers.api.ObservedWatch, EventEmitter]
        ) = {}
        self._event_queues = collections.defaultdict[
            watchdog.observers.api.ObservedWatch,
            EventQueue,
        ](EventQueue)
        self._watch_count = collections.defaultdict[
            watchdog.observers.api.ObservedWatch, int](int)

    @contextlib.asynccontextmanager
    async def open(
        self,
        path: str,
        recursive: bool = False,
    ) -> collections.abc.AsyncIterator[EventQueue]:
        event_queue = await self.schedule(path, recursive)
        try:
            yield event_queue
        finally:
            await self.unschedule(path, recursive)

    async def schedule(
        self,
        path: str,
        recursive: bool = False,
    ) -> EventQueue:
        watch = watchdog.observers.api.ObservedWatch(path, recursive)
        self._watch_count[watch] += 1
        try:
            event_queue = self._event_queues[watch]
            if self._emitters.get(watch) is None:
                emitter = self._emitters[watch] = self._emitter_class(
                    typing.cast(
                        watchdog.observers.api.EventQueue, event_queue
                    ),
                    watch,
                    self.timeout,
                )
                emitter.start()
            return event_queue
        except:
            await self.unschedule(path, recursive)
            raise

    async def unschedule(
        self,
        path: str,
        recursive: bool = False,
    ) -> None:
        watch = watchdog.observers.api.ObservedWatch(path, recursive)
        self._watch_count[watch] -= 1
        if self._watch_count[watch]:
            return
        # Pop all data referencing `watch` before switching context.
        self._watch_count.pop(watch, None)
        emitter = self._emitters.pop(watch, None)
        event_queue = self._event_queues.pop(watch, None)
        try:
            if emitter is not None and emitter.is_alive():
                emitter.stop()
                await emitter.async_join()
        finally:
            # The emitter may still emit events until it is stopped.
            # So only stop the queue when the emitter is fully stopped.
            if event_queue is not None:
                event_queue.stop()


def _get_InotifyFullEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.inotify

    class Emitter(
        EventEmitter,
        watchdog.observers.inotify.InotifyFullEmitter,
    ):
        pass

    return Emitter


def _get_InotifyEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.inotify

    class Emitter(
        EventEmitter,
        watchdog.observers.inotify.InotifyEmitter,
    ):
        pass

    return Emitter


class InotifyObserver(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        generate_full_events: bool = False,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = (
            _get_InotifyFullEmitter()
            if generate_full_events else _get_InotifyEmitter()
        )
        super().__init__(Emitter, timeout, *args, **kwargs)


def _get_PollingEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.polling

    class Emitter(
        EventEmitter,
        watchdog.observers.polling.PollingEmitter,
    ):
        pass

    return Emitter


class PollingObserver(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_PollingEmitter()
        super().__init__(Emitter, timeout, *args, **kwargs)


def _get_PollingObserverVFS(
    stat: collections.abc.Callable[[str], typing.Any],
    listdir: collections.abc.Callable[[str], typing.Any],
) -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.polling

    class Emitter(
        EventEmitter,
        watchdog.observers.polling.PollingEmitter,
    ):

        def __init__(
            self, *args: typing.Any, **kwargs: typing.Any
        ) -> None:
            super().__init__(stat=stat, listdir=listdir, *args, **kwargs)

    return Emitter


class PollingObserverVFS(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        stat: collections.abc.Callable[[str], typing.Any],
        listdir: collections.abc.Callable[[str], typing.Any],
        polling_interval: float = 1,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_PollingObserverVFS(stat=stat, listdir=listdir)
        super().__init__(Emitter, polling_interval, *args, **kwargs)


def _get_FSEventsEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.fsevents

    class Emitter(
        EventEmitter,
        watchdog.observers.fsevents.FSEventsEmitter,
    ):
        pass

    return Emitter


class FSEventsObserver(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_FSEventsEmitter()
        super().__init__(Emitter, timeout, *args, **kwargs)


def _get_FSEventsEmitter2() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.fsevents2

    class Emitter(
        EventEmitter,
        watchdog.observers.fsevents2.FSEventsEmitter,
    ):
        pass

    return Emitter


class FSEventsObserver2(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_FSEventsEmitter2()
        super().__init__(Emitter, timeout, *args, **kwargs)


def _get_KqueueEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.kqueue

    class Emitter(
        EventEmitter,
        watchdog.observers.kqueue.KqueueEmitter,
    ):
        pass

    return Emitter


class KqueueObserver(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_KqueueEmitter()
        super().__init__(Emitter, timeout, *args, **kwargs)


def _get_WindowsApiEmitter() -> type[EventEmitter]:  # pragma: no cover
    import watchdog.observers.read_directory_changes

    class Emitter(
        EventEmitter,
        watchdog.observers.read_directory_changes.WindowsApiEmitter,
    ):
        pass

    return Emitter


class WindowsApiObserver(BaseObserver):  # pragma: no cover

    def __init__(
        self,
        timeout: float = watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        Emitter = _get_WindowsApiEmitter()
        super().__init__(Emitter, timeout, *args, **kwargs)


# Coverage depends on operating system.
if typing.TYPE_CHECKING:  # pragma: no cover
    Observer = PollingObserver
else:  # pragma: no cover
    _system = platform.system()
    if _system == 'Linux':
        try:
            _get_InotifyEmitter()
            Observer = InotifyObserver
        except watchdog.utils.UnsupportedLibc:
            _get_PollingEmitter()
            Observer = PollingObserver
    elif _system == 'Darwin':
        try:
            _get_FSEventsEmitter()
            Observer = FSEventsObserver
        # Catching Exception as the original library does.
        # Possibly because that was what dependencies raised.
        except Exception:  # pylint: disable=broad-except
            try:
                _get_KqueueEmitter()
                Observer = KqueueObserver
                warnings.warn(
                    'Failed to import fsevents.'
                    ' Fall back to kqueue'
                )
            except Exception:  # pylint: disable=broad-except
                _get_PollingEmitter()
                Observer = PollingObserver
                warnings.warn(
                    'Failed to import fsevents and kqueue.'
                    ' Fall back to polling.'
                )
    elif _system == 'FreeBsd':
        _get_KqueueEmitter()
        Observer = KqueueObserver
    elif _system == 'Windows':
        try:
            _get_WindowsApiEmitter()
            Observer = WindowsApiObserver
        except Exception:  # pylint: disable=broad-except
            _get_PollingEmitter()
            Observer = PollingObserver
            warnings.warn(
                'Failed to import read_directory_changes.'
                ' Fall back to polling.'
            )
    else:
        _get_PollingEmitter()
        Observer = PollingObserver
