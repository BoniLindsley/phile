#!/usr/bin/env python3

# Standard library.
import datetime
import logging
import pathlib
import signal
import sys
import typing

# External dependencies.
from PySide2.QtCore import QEvent, QEventLoop, Qt
from PySide2.QtCore import Signal, SignalInstance, Slot
from PySide2.QtGui import (
    QCloseEvent, QHideEvent, QResizeEvent, QShowEvent, QPalette
)
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QTextEdit
)
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
from phile.notify.notification import Notification
import phile.trigger
import phile.PySide2_extras.event_loop
import phile.PySide2_extras.posix_signal

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class NotificationMdiSubWindow(QMdiSubWindow):

    closed = typing.cast(SignalInstance, Signal(str))
    """Emitted when the sub-window is closed."""

    def __init__(
        self, *, name: str, creation_datetime: datetime.datetime,
        content: str
    ):
        super().__init__()
        content_widget = QTextEdit()
        content_widget.setReadOnly(True)
        self.setWidget(content_widget)
        # Set the size now so that parent QMdiArea
        # can use it to position sub-windows in resize events.
        self.adjustSize()
        # By default, clicking the close window button hides it.
        # This makes sure it gets "closed" properly.
        self.setAttribute(Qt.WA_DeleteOnClose)
        # Create variables for storing properties,
        # so that setups, such as window title modification, can use it.
        self._creation_datetime = creation_datetime
        # Remember remaining given properties.
        self.content = content
        self.is_read = False
        self.name = name

    def changeEvent(self, change_event: QEvent) -> None:
        super().changeEvent(change_event)
        if change_event.type() != QEvent.WindowStateChange:
            return
        # States: minimised, maximised, fullscreen and active.
        # Only the first two are handled.
        #
        # Windows can switch between active and inactive
        # without needing repositioning.
        # So that is ignored.
        #
        # Not sure what fullscreen would mean for a sub-window..?
        min_max_state = Qt.WindowMaximized | Qt.WindowMinimized
        old_min_max_state = change_event.oldState() & min_max_state
        new_min_max_state = self.windowState() & min_max_state
        if old_min_max_state == new_min_max_state:
            _logger.debug('Sub-window not min-maxiimized.')
            return
        _logger.debug('Sub-window min-maximized: re-tiling parent.')
        self._retile_parent()

    def closeEvent(self, close_event: QCloseEvent) -> None:
        """Internal method to handle the sub-window being closed. """
        self.closed.emit(self.name)

    @property
    def content(self) -> str:
        return self.widget().toPlainText()

    @content.setter
    def content(self, new_content: str) -> None:
        self.widget().setPlainText(new_content)

    @property
    def creation_datetime(self) -> datetime.datetime:
        return self._creation_datetime

    @creation_datetime.setter
    def creation_datetime(self, new_create_datetime) -> None:
        self._creation_datetime = new_create_datetime
        self.refresh_window_title()

    def hideEvent(self, hide_event: QHideEvent):
        # When a sub-window is hidden, a re-tile is necessary
        # to fill any gaps left by the hidden widget.
        # It is possible to hide without closing a widget.
        # So we need to handle the hide event explicitly.
        _logger.debug('Sub-window hidden: default handling.')
        super().hideEvent(hide_event)
        _logger.debug('Sub-window hidden: re-tiling parent.')
        self._retile_parent()

    @property
    def is_read(self) -> bool:
        content_widget = self.widget()
        content_palette = content_widget.palette()
        text_color = content_palette.color(QPalette.Text)
        disabled_text_color = content_palette.color(
            QPalette.Disabled, QPalette.WindowText
        )
        return text_color == disabled_text_color

    @is_read.setter
    def is_read(self, new_is_read: bool) -> None:
        content_widget = self.widget()
        content_palette = content_widget.palette()
        base_color = content_palette.color(QPalette.Window)
        text_color = content_palette.color(
            QPalette.Disabled if new_is_read else QPalette.Active,
            QPalette.WindowText
        )
        content_palette.setColor(QPalette.Text, text_color)
        content_palette.setColor(QPalette.Base, base_color)
        content_widget.setPalette(content_palette)

    @property
    def name(self) -> str:
        return self.widget().documentTitle()

    @name.setter
    def name(self, new_name: str) -> None:
        self.widget().setDocumentTitle(new_name)
        self.refresh_window_title()

    def refresh_window_title(self) -> None:
        self.setWindowTitle(
            self.name + '--' + self.creation_datetime.strftime('%c')
        )

    def _retile_parent(self) -> None:
        mdi_area = self.mdiArea()
        if mdi_area is not None:
            mdi_area._tile_sub_windows_vertically()

    def showEvent(self, show_event: QShowEvent):
        _logger.debug('Sub-window shown: default handling.')
        super().showEvent(show_event)
        # Showing a widget typically also activates it by default.
        # So handling activation event (or window state change events)
        # might seem sufficient.
        # However, it is possible to show a widget without activating it.
        # So we need to handle show events explicitly.
        # We need to make sure that showing a sub-window would re-tile
        # so it goes into the correct position.
        _logger.debug('Sub-window shown: re-tiling parent.')
        self._retile_parent()


class NotificationMdi(QMdiArea):

    def __init__(self, *args, **kwargs):
        _logger.debug('Creating notification MDI.')
        super().__init__(*args, **kwargs)
        self.setActivationOrder(QMdiArea.CreationOrder)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def add_notification(self, *args, **kwargs) -> QMdiSubWindow:
        _logger.debug(
            'Adding notification sub-window. Total will be %s.',
            len(self.subWindowList()) + 1
        )
        return super().addSubWindow(
            NotificationMdiSubWindow(*args, **kwargs)
        )

    def resizeEvent(self, resize_event: QResizeEvent):
        _logger.debug('Resized: default handling.')
        super().resizeEvent(resize_event)
        _logger.debug('Resized: re-tiling.')
        self._tile_sub_windows_vertically(area_size=resize_event.size())

    def showEvent(self, show_event: QShowEvent):
        _logger.debug('Shown: default handling.')
        super().showEvent(show_event)
        _logger.debug('Shown: re-tiling.')
        self._tile_sub_windows_vertically()

    def _tile_sub_windows_vertically(self, *, area_size=None):
        _logger.debug('Tiling sub-window vertically.')
        # This method gets called many times when shutting down,
        # once for each widget because hiding this widget
        # hides every sub-window.
        # So early exit in those cases,
        # since the effect would not be visible anyway.
        if self.isHidden():
            _logger.debug('MDI not tiling: hidden.')
            return
        # The alternative is TabbedView mode.
        # Moving sub-windows around in that mode
        # would break the tabbbed view.
        if self.viewMode() != QMdiArea.SubWindowView:
            _logger.debug('MDI not tiling: not in sub-window mode.')
            return

        if area_size is None:
            area_size = self.size()

        window_width = area_size.width()
        vertical_offset = 0
        tile_window_list = [
            window for window in self.subWindowList()
            if not window.isMinimized() and not window.isMaximized()
            and window.isVisible()
        ]
        _logger.debug('Tiling %s sub-windows.', len(tile_window_list))
        for window in tile_window_list:
            height = window.height()
            window.move(0, vertical_offset)
            window.resize(window_width, height)
            vertical_offset += height
        _logger.debug('Finished tiling.')


class MainWindow(QMainWindow):

    _closed = typing.cast(SignalInstance, Signal())
    """Internal. Emitted when the window is closed to handle cleanup."""

    def __init__(
        self, *args, configuration: phile.configuration.Configuration,
        watching_observer: watchdog.observers.Observer, **kwargs
    ):
        # Create the window.
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_DeleteOnClose)
        # Create the GUI for displaying notifications.
        mdi_area = NotificationMdi()
        self.setCentralWidget(mdi_area)
        # Keep track of sub-windows by name
        # so that we know which ones to modify when files are changed.
        self._sub_windows: typing.Dict[Notification,
                                       NotificationMdiSubWindow] = {}
        # Figure out where notifications are and their suffix.
        self._configuration = configuration
        # Set up tray directory monitoring.
        self.set_up_notify_event_handler(
            watching_observer=watching_observer
        )
        self.set_up_trigger_event_handler(
            watching_observer=watching_observer
        )

    def set_up_notify_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ) -> None:
        # Forward watchdog events into Qt signal and handle it there.
        call_soon = (
            phile.PySide2_extras.event_loop.CallSoon(
                parent=self,
                call_target=self.on_file_system_event_detected,
            )
        )
        # Use a scheduler to toggle the event handling on and off.
        dispatcher = phile.watchdog_extras.Dispatcher(
            event_handler=call_soon
        )
        watched_path = self._configuration.notification_directory
        watched_path.mkdir(exist_ok=True, parents=True)
        self._notify_scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=dispatcher,
            watched_path=watched_path,
            watching_observer=watching_observer,
        )
        # Make sure to remove handler from observer
        # when ``self`` is closed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(self._notify_scheduler.unschedule)
        self._closed.connect(self._notify_scheduler.unschedule)

    def set_up_trigger_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ) -> None:
        # Take cooperative ownership of the directory
        # containing trigger file for trays.
        self._entry_point = phile.trigger.EntryPoint(
            configuration=self._configuration,
            trigger_directory=pathlib.Path('phile-notify-gui'),
        )
        self._entry_point.bind()
        self.destroyed.connect(self._entry_point.unbind)
        # Turn file system events into trigger names to process.
        event_conveter = phile.trigger.EventConverter(
            configuration=self._configuration,
            trigger_handler=self.process_trigger,
        )
        # Forward watchdog events into Qt signal and handle it there.
        call_soon = (
            phile.PySide2_extras.event_loop.CallSoon(
                parent=self,
                call_target=event_conveter,
            )
        )
        # Filter out non-trigger activation events
        # to reduce cross-thread communications.
        event_filter = phile.trigger.EventFilter(
            configuration=self._configuration,
            event_handler=call_soon,
            trigger_directory=self._entry_point.trigger_directory,
        )
        # Use a scheduler to toggle the event handling on and off.
        dispatcher = phile.watchdog_extras.Dispatcher(
            event_handler=event_filter
        )
        self._trigger_scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=dispatcher,
            watched_path=self._entry_point.trigger_directory,
            watching_observer=watching_observer,
        )
        self._trigger_scheduler.schedule()
        # Make sure to remove handler from observer
        # when ``self`` is closed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(self._trigger_scheduler.unschedule)
        self._closed.connect(self._trigger_scheduler.unschedule)
        # Allow closing with a trigger.
        self._entry_point.add_trigger('close')
        self._entry_point.add_trigger('show')

    def process_trigger(self, trigger_name: str) -> None:
        _logger.debug('MainWindow trigger %s.', trigger_name)
        if trigger_name == 'hide':
            self.hide()
        elif trigger_name == 'show':
            self.show()
        elif trigger_name == 'close':
            self.close()
        else:
            _logger.warning('Unknown trigger command: %s', trigger_name)

    def closeEvent(self, close_event: QCloseEvent) -> None:
        """Internal. Handle cleanup."""
        _logger.debug('MainWindow is closing.')
        self._closed.emit()

    def hideEvent(self, hide_event: QHideEvent) -> None:
        _logger.debug('MainWindow is hiding.')
        self._notify_scheduler.unschedule()
        self._entry_point.remove_trigger('hide')
        self._entry_point.add_trigger('show')

    def showEvent(self, show_event: QShowEvent) -> None:
        _logger.debug('MainWindow is showing.')
        # Start scheduling first to not miss events.
        self._notify_scheduler.schedule()
        # Initialise by filling in existing notifications.
        # There is a possibility of race condition
        # between the file monitor starting
        # and fetching a list of existing files,
        # I am not sure if there is much that can be done about it,
        # other than making sure the the listing occurs
        # as soon as possible after starting the file monitor.
        # There is cooperative locking,
        # but that seems over-engineered for the task at hand.
        configuration = self._configuration
        notification_directory = configuration.notification_directory
        for notification_path in notification_directory.iterdir():
            if notification_path.is_file():
                self.on_file_system_event_detected(
                    watchdog.events.FileCreatedEvent(notification_path)
                )
        self._entry_point.remove_trigger('show')
        self._entry_point.add_trigger('hide')

    @Slot(watchdog.events.FileSystemEvent)  # type: ignore[operator]
    def on_file_system_event_detected(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        _logger.debug('Watchdog event received.')
        # Notifications are files. Directory changes do not matter.
        if watchdog_event.is_directory:
            _logger.debug('Watchdog event: not using directory events.')
            return
        # Consider a move event as a delete and create.
        event_type = watchdog_event.event_type
        if event_type == watchdog.events.EVENT_TYPE_MOVED:
            _logger.debug('Watchdog event: notification moved.')
            for new_event in [
                watchdog.events.FileDeletedEvent(
                    watchdog_event.src_path
                ),
                watchdog.events.FileCreatedEvent(
                    watchdog_event.dest_path
                )
            ]:
                self.on_file_system_event_detected(new_event)
            return
        # Only files of a specific extension is a notification.
        try:
            notification = Notification(
                configuration=self._configuration,
                path=pathlib.Path(watchdog_event.src_path)
            )
        except Notification.SuffixError as error:
            _logger.debug('Watchdog event: %s', error)
            return
        # Determine what to do base on existence of the actual file.
        self.load(notification)

    def load(self, notification: Notification) -> None:
        # Figure out if the notification was tracked.
        sub_window = self._sub_windows.get(notification, None)
        # Try to load the notification.
        notification_exists = True
        try:
            new_data = {
                "content": notification.read(),
                "creation_datetime": notification.creation_datetime,
                "name": notification.name,
            }
        except FileNotFoundError:
            notification_exists = False
        # If the notification does not exist,
        # either remove the subwindow or there is nothing to do.
        if not notification_exists:
            if sub_window is not None:
                del self._sub_windows[notification]
                sub_window.deleteLater()
        # Can assume from here that the notification is loaded.
        elif sub_window is not None:
            for key, value in new_data.items():
                setattr(sub_window, key, value)
        else:
            sub_window = self.centralWidget().add_notification(
                **new_data
            )
            sub_window.show()
            sub_window.closed.connect(
                self.on_notification_sub_window_closed
            )
            self._sub_windows[notification] = sub_window

    def on_notification_sub_window_closed(
        self, notification_name: str
    ) -> None:
        notification = Notification(
            configuration=self._configuration, name=notification_name
        )
        notification.remove()
        self.load(notification)


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    app = QApplication(argv)
    configuration = phile.configuration.Configuration()
    watching_observer = watchdog.observers.Observer()
    watching_observer.daemon = True
    watching_observer.start()
    main_window = MainWindow(
        configuration=configuration, watching_observer=watching_observer
    )
    main_window.show()
    posix_signal = phile.PySide2_extras.posix_signal.PosixSignal(
        main_window
    )
    posix_signal.signal_received.connect(main_window.close)
    phile.PySide2_extras.posix_signal.install_noop_signal_handler(
        signal.SIGINT
    )
    return app.exec_()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
