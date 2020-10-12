#!/usr/bin/env python3

# Standard library.
import logging
import pathlib
import typing

# External dependencies.
from PySide2.QtCore import QChildEvent, QCoreApplication, QEvent, QObject
from PySide2.QtCore import Signal  # type: ignore
import watchdog.events  # type: ignore
import watchdog.observers  # type: ignore

# Internal package.
from phile.watchdog_extras import Observer

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class FileSystemSignalEmitter(QObject):
    """Forwards watchdog events as singals in PySide2 event loop."""

    _watchdog_event_dispatch = QEvent.Type(  # type: ignore
        QEvent.registerEventType()
    )
    """Internal. An event wrapping watchdog dispatched events."""
    file_system_event_detected = Signal(watchdog.events.FileSystemEvent)
    """Signals there are changes in the monitored path."""

    def __init__(
        self,
        *args,
        monitored_path: pathlib.Path,
        recursive: bool = False,
        **kwargs
    ):
        self._monitoring_observer: typing.Optional[Observer] = None
        self._monitored_path = monitored_path
        self._watchdog_watch = watchdog.observers.api.ObservedWatch(
            path=str(monitored_path), recursive=recursive
        )
        super().__init__(*args, **kwargs)
        self.destroyed.connect(
            lambda: self.stop() if self.is_started() else None
        )

    def dispatch(self, watchdog_event: watchdog.events.FileSystemEvent):
        _logger.debug('Watchdog dispatching event.')
        event_to_post = QEvent(self._watchdog_event_dispatch)
        event_to_post.watchdog_event = watchdog_event
        QCoreApplication.postEvent(self, event_to_post)

    def event(self, event_to_handle) -> bool:
        if event_to_handle.type() != self._watchdog_event_dispatch:
            return super().event(event_to_handle)
        _logger.debug('Signal emitter: emitting watchdog event.')
        self.file_system_event_detected.emit(  # type: ignore
            event_to_handle.watchdog_event
        )
        return True

    def is_started(self) -> bool:
        """
        Whether this emitter is set to forward file system events.

        This does not take into account whether the parent monitor
        is set to provide the file system events to forward.
        """
        return self._monitoring_observer is not None

    def start(self, *, _monitoring_observer: Observer = None) -> None:
        """
        Start forwarding watchdog events to PySide2 signals.

        :param Observer _observer:
            If not given, `parent()` must be a `FileSystemEvent`,
            and its underlying `Observer` will be used instead.

        Note that, if the `monitoring_observer` is not `start`-ed,
        then this emitter does not receive events to forward.
        The `monitoring_observer` can be `start`-ed before or after this.

        It is possible to use an emitter directly
        as a handler in an observer.
        Using the emitter in that way bypasses lifetime management
        offered by PySide2 object ownership tree.
        It is up to the caller to, before this is destroyed,
        remove the emitter as a handler
        or stop the observer first as appropriate.
        """
        _logger.debug('Emitter starting.')
        if self.is_started():
            _logger.debug('Emitter already started. Not starting.')
            return
        if _monitoring_observer is None:
            parent = self.parent()
            if not isinstance(parent, FileSystemMonitor):
                raise RuntimeError(
                    'Emitter parent is not a monitor. Not starting.'
                )
            _logger.debug('Emitter using parent observer.')
            _monitoring_observer = parent._watchdog_observer
        _logger.debug('Emitter starting.')
        self._watchdog_watch = _monitoring_observer.add_handler(
            self,
            self._monitored_path,
            self._watchdog_watch.is_recursive,
        )
        self._monitoring_observer = _monitoring_observer

    def stop(self) -> None:
        _logger.debug('Emitter stopping.')
        if not self.is_started():
            _logger.debug('Emitter not started. Not stopping.')
            return
        assert self._monitoring_observer is not None  # For mypy.
        self._monitoring_observer.remove_handler(
            self, self._watchdog_watch
        )
        self._monitoring_observer = None
        _logger.debug('Emitter stopped.')


class FileSystemMonitor(QObject):
    """
    Provides file monitoring for FileSystemSignalEmitter children.

    Children that are `FileSystemSignalEmitter`-s
    are not automatically `start`-ed
    when they set a `FileSystemMonitor` as parent
    even if the parent was already`start`-ed.
    However, when the parent `FileSystemMonitor` `start`-s,
    then all child `FileSystemSignalEmitter`-s `start` automatically.
    This is consistent with the behaviour of `QWidget.show`.
    Similarly, for the same consistency,
    when the parent of a `FileSystemSignalEmitter` is changed,
    it is automatically `stop`-ped.

    .. admonition:: Implementation detail

       This behaviour is chosen mostly because of PySide2 constraints.
       The childre given when processing `ChildAddedEvent`-s
       are not guaranteed to be completely constructed.
       It happens, for example, if the `FileSystemSignalEmitter`
       is given its `parent` to pass to its `QObject` constructor.
       This makes implementing automatic `start` error prone.

       It is necessary to `stop` child `FileSystemSignalEmitter`-s
       when they are no longer children of a `FileSystemMonitor`
       because `FileSystemMonitor`, or rather the underlying `Observer`,
       uses `FileSystemSignalEmitter` as an event handler.
       In particular, if the lifetime of the child ends
       before that of the parent `FileSystemMonitor`,
       then the event handler becomes invalid.

       There are three ways a child `FileSystemSignalEmitter`
       may stop being a child of a `FileSystemMonitor`.
       The first is `setParent` to a different `QObject`..
       In this case, a `ChildRemovedEvent`
       is posted to the parent `FileSystemMonitor`,
       and the parent can `stop` the child from there.

       The second way is via `deleteLater`.
       When the deletion request is processed (later on after the call),
       an internal `setParent` call is used,
       but this occurs in the C++ destructor of `QObject` --
       the child will no longer be `FileSystemSignalEmitter`,
       In particular, the parent will not be able
       to access `FileSystemSignalEmitter.stop`
       in the `ChildRemovedEvent`.
       The `stop`-ping then has to happen
       in the children `destroyed` signal.
       Instead of a slot of the child or the parent,
       the signal is connected to a `stop` lambda managed by the child,
       also as opposed to one managed by the parent.
       If it is a slot of the child,
       then the destructor `disconnect`-s the slot
       and the slot would not be called.
       If the `stop`-ping is managed by the parent,
       then the `ChildRemovedEvent` would have to `disconnect` it
       (to handle the first way above),
       which means the parent has to keep track
       of the child Python object (in the slot case)
       or a `stop` lambda` (in the lambda case),
       and the parent has to manage an extra collection of data.
       It makes sense, then, to let the child manage it,
       though it requires the child keeping track of the `Observer` used,
       which is eaiser to manage.

       A third way is the parent being `destroyed`.
       In this case, ensuring its `Observer`
       would not dispatch to its children should be sufficient,
       since all object would be `destroyed` anyway.
       This means `stop`-ping the `Observer` on `destroyed`.
       Current PySide2 implementation has delete children
       after the parent `destroyed` signal is processed,
       and so there is no race condition of `Observer`
       using `destroyed` child emitters as handlers.
    """

    def __init__(
        self, *args, _watchdog_observer: Observer = None, **kwargs
    ):
        """
        :param Observer _watchdog_observer:
            Internal.
            Takes ownership of the given observer.
            The `start` and `stop` status of this monitor
            inherits the status-es of the given `Observer`.
            For example, if the given `Observer` is `start`-ed already,
            then this monitor cannot `start`-ed anymore,
            as it is already considered `start`-ed.
        """
        super().__init__(*args, **kwargs)

        if _watchdog_observer is None:
            _logger.debug('Monitor creating its own observer.')
            _watchdog_observer = Observer()

        self._watchdog_observer = _watchdog_observer
        """The underlying file system observer to monitor changes."""

        self.destroyed.connect(
            lambda: self._watchdog_observer.stop() if self.
            was_start_called() and not self.was_stop_called() else None
        )

    def childEvent(self, child_event: QChildEvent) -> None:
        """Internal. Stop emitters when they are removed as children."""
        # Do not try to start monitoring
        # if child's class is not as expected.
        child = child_event.child()
        if not isinstance(child, FileSystemSignalEmitter):
            _logger.debug('Monitor child not emitter.')
            super().childEvent(child_event)
            return
        # Start or stop monitoring as necessary.
        event_type = child_event.type()
        if event_type == QEvent.ChildRemoved:
            child.stop()

    def was_start_called(self) -> bool:
        return self._watchdog_observer.was_start_called()

    def was_stop_called(self) -> bool:
        return self._watchdog_observer.was_stop_called()

    def start(self) -> None:
        """
        Start forwarding file system messages to child emitters.

        A monitor can only be `start`-ed once.
        """
        if self.was_stop_called():
            raise RuntimeError('Monitor not starting. Already stopped.')
        if self.was_start_called():
            _logger.debug('Monitor not starting. Alredy started.')
            return
        _logger.debug('Monitor starting children.')
        for child in self.children():
            if isinstance(child, FileSystemSignalEmitter):
                child.start(_monitoring_observer=self._watchdog_observer)
        self._watchdog_observer.start()

    def stop(self) -> None:
        if not self.was_start_called():
            raise RuntimeError('Monitor not stopping. Not started.')
        if self.was_stop_called():
            _logger.debug('Monitor not stopping. Already stopped.')
            return
        _logger.debug('Monitor stopping observer.')
        self._watchdog_observer.stop()
        # It is technically not necessary to stop the children
        # since the children keeps a reference to the Observer
        # and can remove themselves as handlers as necessary.
        # That would in fact help
        # with not having to clean-up on shut down.
        # However, for consistency with `QWidget.show`,
        # it is better to `stop` the child emitters anyway.
        _logger.debug('Monitor stopping children.')
        for child in self.children():
            if isinstance(child, FileSystemSignalEmitter):
                child.stop()
