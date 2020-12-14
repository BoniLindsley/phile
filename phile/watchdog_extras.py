#!/usr/bin/env python3
"""
-------------------------
watchdog observer wrapper
-------------------------
"""

# Standard library.
import pathlib
import types
import typing

# External dependencies.
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

_D_co = typing.TypeVar('_D_co', covariant=True)
_D_contra = typing.TypeVar('_D_contra', contravariant=True)


class SingleParameterCallback(typing.Protocol[_D_contra, _D_co]):
    """
    Replacement for ``Callable[[_D_contra], _D_co]``.

    Calling a callable member is not handled correctly by mypy yet.
    Specifically, ``self.load(0)`` is treated as a two-argument call
    even if ``self.load`` is a callable variable.
    See: https://github.com/python/mypy/issues/708#issuecomment-667989040
    """

    def __call__(self, __arg_1: _D_contra) -> _D_co:
        ...


EventHandler = (
    SingleParameterCallback[watchdog.events.FileSystemEvent, typing.Any]
)
"""
Signature of callables
receiveing :class:`~watchdog.events.FileSystemEvent`-s.
"""

PathHandler = SingleParameterCallback[pathlib.Path, typing.Any]
"""
Signature of callables for processing a :class:`~pathlib.Path`.
"""

PathFilter = SingleParameterCallback[pathlib.Path, bool]
"""
Signature of callables for pre-process :class:`~pathlib.Path`-s checking.
"""


class Observer(watchdog.observers.Observer):
    """
    Monitors for file system events and notify interested handlers.

    .. admonition:: Raison d'être

       The parent class :attr:`~watchdog.observers.Observer`
       provides :meth:`~watchdog.observers.api.BaseObserver.schedule`
       and
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       for registering,
       and :meth:`~watchdog.observers.api.BaseObserver.unschedule` and
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       for deregistering,
       as being interested in certain file or directory changes.

       The :meth:`~watchdog.observers.api.BaseObserver.schedule` method
       sets up file monitoring of the given ``path``,
       and remembers which handlers to call for the ``path``.
       The
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`
       method does the same except it does not do the setting up.
       For predictability reasons,
       since :meth:`~watchdog.observers.api.BaseObserver.schedule`
       skips the setting up if its was already done,
       it should always be used over
       :meth:`~watchdog.observers.api.BaseObserver.add_handler_for_watch`,
       otherwise the handler may be registered against no monitoring
       except in simple use cases,
       or if the user does their own redundant tracking
       of :attr:`~watchdog.observers.api.ObservedWatch.path`-s.

       On the clean-up end,
       the :meth:`~watchdog.observers.api.BaseObserver.unschedule` method
       unregisters all handlers registered for a given
       :class:`~watchdog.observers.api.ObservedWatch`
       and stops monitoring the associated ``path``. whereas
       :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
       removes a single handler
       but without checking if the monitoring should stop.
       The former does not provide fine control over unregistering
       whereas the latter potentially leads to a inotify watch leak.

    This class introduces the :meth:`add_handler`
    and :meth:`remove_handler` methods.
    The latter provides finer control in the sense that
    it stops the monitoring if there are no more handlers registered
    for the given :class:`~watchdog.observers.api.ObservedWatch`.
    bridging functionality gaps
    in :attr:`~watchdog.observers.Observer`.
    It also ignores removal attempts after the observer is stopped.
    The former is identical
    to :meth:`~watchdog.observers.api.BaseObserver.schedule`,
    provided mainly for symmetry of operations,
    except the ``path`` parameter should be a :class:`~pathlib.Path`,
    for potential type checking purposes.

    This class also introduces :meth:`was_start_called`
    and :meth:`was_stop_called`
    to determine the status of the :class:`Observer`.
    They are sometimes useful in determining
    whether an :class:`Observer`
    can be :meth:`~watchdog.observers.api.BaseObserver.start`-ed
    since :meth:`~threading.Thread.start`-ing
    a :class:`~threading.Thread` twice raises an exception.
    """

    def __init__(self, *args, **kwargs):
        """
        Forwards all arguments
        to :attr:`~watchdog.observers.Observer`.

        The underlying :class:`~threading.Thread`
        is set as a :attr:`~threading.Thread.daemon`
        as the file monitoring does not require any mandatory clean-up.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True

    def add_handler(
        self,
        event_handler: watchdog.events.FileSystemEventHandler,
        path: pathlib.Path,
        recursive: bool = False,
    ) -> watchdog.observers.api.ObservedWatch:
        """Notify ``event_handler`` of changes in ``path``."""
        return self.schedule(event_handler, str(path), recursive)

    def has_handlers(self) -> bool:
        return bool(self._handlers)

    def remove_handler(
        self, event_handler: watchdog.events.FileSystemEventHandler,
        watch: watchdog.observers.api.ObservedWatch
    ) -> None:
        """
        Stop notifying ``event_handler`` of changes in ``watch``.

        This is an implementation-specific work-around
        as it uses underscore variables.
        It merges
        :meth:`~watchdog.observers.api.BaseObserver.remove_handler_for_watch`
        and :meth:`~watchdog.observers.api.BaseObserver.unschedule`.
        """
        with self._lock:
            handlers = self._handlers.get(watch)
            if not handlers:
                return
            handlers.remove(event_handler)
            if not handlers:
                emitter = self._emitter_for_watch[watch]
                del self._handlers[watch]
                self._remove_emitter(emitter)
                self._watches.remove(watch)

    def was_start_called(self) -> bool:
        return self.ident is not None

    def was_stop_called(self) -> bool:
        return self._stopped_event.is_set()


class Scheduler(watchdog.events.FileSystemEventHandler):
    """
    Represents whether a :data:`PathHandler`
    is :meth:`~watchdog.observers.api.BaseObserver.schedule`-d
    to receive paths of file system events
    from an :attr:`~watchdog.observers.Observer`.

    Each instane remembers infomation necessary
    to start watching a directory or file
    so that starting requires only a single method call.

    There is a delay between the event being detected
    and the event being processed.
    This time may be sufficient for the files involved to be deleted
    or changed into a directory, etc.
    So the event type itself is not so useful.
    In particular, the user of file system events
    needs to handle such cases anyway at the point of file access.
    So the only reliable data from the event are the file paths
    indicating that some changes occured to the files of the path.
    It is then up to the user to determine what to do with the path
    depending on whether the path still exists, is still a file,
    has valid data or was already known about using their own data.
    So this scheduler accepts a handler that takes paths as an parameter
    instead of file system events.
    """

    def __init__(
        self,
        *args,
        path_filter: PathFilter = lambda _: True,
        path_handler: PathHandler = lambda _: None,
        watch_recursive: bool = False,
        watched_path: pathlib.Path,
        watching_observer: watchdog.observers.Observer,
        **kwargs,
    ) -> None:
        """
        :param PathFilter path_filter:
            A callback that returns :data:`True`
            if a given :class:`pathlib.Path`
            should be passed on to :data:`path_handlers`.
        :param bool watch_recursive:
            Whether to watch subdirectories of ``watched_path``
            if ``watched_path`` is a directory.
        :param ~PathHandler path_handler:
            Handler to dispatched event paths to
            when there are changes to ``watched_path``.
        :param ~pathlib.Path watched_path:
            Path to watch for changes.
        :param watching_observer:
            The instance that dispatches events to ``path_handler``.
        :type watching_observer: :attr:`~watchdog.observers.Observer`
        """
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.watch_recursive = watch_recursive
        self.watched_path = watched_path
        self.path_filter = path_filter
        """Callable determining whether a paths hould be dispatched."""
        self.path_handler = path_handler
        """Callable for forward event dispatch to."""
        self.watching_observer = watching_observer
        """
        The :attr:`watchdog.observers.Observer` instance
        to which ``path_handler`` is to be scheduled in.
        """
        self.watchdog_watch: typing.Optional[
            watchdog.observers.api.ObservedWatch] = None
        """Description of watch data from :mod:`watchdog`."""

    def __enter__(self) -> 'Scheduler':
        self.schedule()
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self.unschedule()
        return None

    @property
    def is_scheduled(self) -> bool:
        """
        Returns whether :data:`watching_observer`
        is set to forward paths to :data:`path_handler`.
        """
        return self.watchdog_watch is not None

    def schedule(self) -> None:
        """Schedule events to be dispatched to :data`path_handler`."""
        if not self.is_scheduled:
            self.watched_path.mkdir(exist_ok=True, parents=True)
            self.watchdog_watch = self.watching_observer.schedule(
                self, str(self.watched_path), self.watch_recursive
            )

    def unschedule(self) -> None:
        """Stop dispatching events to `path_handler``."""
        if not self.is_scheduled:
            return
        watching_observer = self.watching_observer
        # This should ideally have been just::
        #
        #     self.watching_observer.remove_handle_for_watch(
        #         self,
        #         self.watchdog_watch,
        #     )
        #
        # But there is a potential inotify watch leak
        # since it does not remove emitters with no handlers.
        # This is an implementation-specific work-around
        # as it uses underscore variables.
        # It merges behaviour of `remove_handler_for_watch`
        # with that of `unschedule`.
        # Calling one after the other creates a race condition
        # since each of them acquire a lock,
        # and there might be state changes in between their locking.
        # Alternatively, we can accept only `watchdog_extras.Observer`
        # but that is not particularly flexible.
        watchdog_watch = self.watchdog_watch
        self.watchdog_watch = None
        with watching_observer._lock:
            handlers = watching_observer._handlers.get(watchdog_watch)
            if handlers is not None:
                handlers.remove(self)
                if not handlers:
                    watching_observer._remove_handlers_for_watch(
                        watchdog_watch
                    )
                    emitter = watching_observer._emitter_for_watch[
                        watchdog_watch]
                    watching_observer._remove_emitter(emitter)
                    watching_observer._watches.remove(watchdog_watch)

    def dispatch(self, event: watchdog.events.FileSystemEvent) -> None:
        """
        Internal. Calls :data:`path_handler` with paths in the ``event``.

        :param source_event:
            The :class:`~watchdog.events.FileSystemEvent`
            from which to extract file paths.

        The file paths to call :data:`path_handler` with
        are extracted from ``source_event``.
        If ``source_event`` is a directory event,
        it is not called.
        If it is a file move event,
        it is called with an iterator of both file paths
        in an unspecified order.
        Otherwise, its argument iterates through one path.
        """
        if event.is_directory:
            return
        path = pathlib.Path(event.src_path)
        if self.path_filter(path):
            self.path_handler(path)
        if event.event_type != watchdog.events.EVENT_TYPE_MOVED:
            return
        path = pathlib.Path(event.dest_path)
        if self.path_filter(path):
            self.path_handler(path)
