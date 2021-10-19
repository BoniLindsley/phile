#!/usr/bin/env python3
"""
---------------------------------------------
Convenience module for using :mod:`~watchdog`
---------------------------------------------

.. automodule:: phile.watchdog.asyncio
.. automodule:: phile.watchdog.observers
"""

# Standard library.
import pathlib
import types
import typing

# External dependencies.
import watchdog.events
import watchdog.observers

# Internal packages.
import phile.watchdog.observers

_D_co = typing.TypeVar("_D_co", covariant=True)
_D_contra = typing.TypeVar("_D_contra", contravariant=True)


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


EventHandler = SingleParameterCallback[
    watchdog.events.FileSystemEvent, typing.Any
]
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


class Scheduler(watchdog.events.FileSystemEventHandler):
    """
    Represents whether a :data:`PathHandler`
    is :meth:`~watchdog.observers.api.BaseObserver.schedule`-d
    to receive paths of file system events
    from an :attr:`~watchdog.observers.api.BaseObserver`.

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
        *args: typing.Any,
        path_filter: PathFilter = lambda _: True,
        path_handler: PathHandler = lambda _: None,
        watch_recursive: bool = False,
        watched_path: pathlib.Path,
        watching_observer: watchdog.observers.api.BaseObserver,
        **kwargs: typing.Any,
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
        :type watching_observer: :attr:`~watchdog.observers.api.BaseObserver`
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
        The :attr:`watchdog.observers.api.BaseObserver` instance
        to which ``path_handler`` is to be scheduled in.
        """
        self.watchdog_watch: typing.Optional[
            watchdog.observers.api.ObservedWatch
        ] = None
        """Description of watch data from :mod:`watchdog`."""

    def __enter__(self) -> "Scheduler":
        self.schedule()
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
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
            self.watchdog_watch = phile.watchdog.observers.add_handler(
                observer=self.watching_observer,
                event_handler=self,
                path=self.watched_path,
                recursive=self.watch_recursive,
            )

    def unschedule(self) -> None:
        """Stop dispatching events to `path_handler``."""
        if not self.is_scheduled:
            return
        assert self.watchdog_watch is not None
        phile.watchdog.observers.remove_handler(
            observer=self.watching_observer,
            event_handler=self,
            watch=self.watchdog_watch,
        )
        self.watchdog_watch = None

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
        assert isinstance(event, watchdog.events.FileMovedEvent)
        path = pathlib.Path(event.dest_path)
        if self.path_filter(path):
            self.path_handler(path)
