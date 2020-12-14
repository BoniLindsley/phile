#!/usr/bin/env python3

# Standard library.
import dataclasses
import datetime
import functools
import logging
import pathlib
import signal
import sys
import typing

# External dependencies.
from PySide2.QtCore import QEvent, QEventLoop, Qt
from PySide2.QtCore import Signal, SignalInstance
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
import phile.data
import phile.notify
import phile.trigger
import phile.watchdog_extras
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
        self, *, title: str, modified_at: datetime.datetime, content: str
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
        self._modified_at = modified_at
        # Remember remaining given properties.
        self.content = content
        self.is_read = False
        self.title = title

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
        self.closed.emit(self.title)

    @property
    def content(self) -> str:
        return self.widget().toPlainText()

    @content.setter
    def content(self, new_content: str) -> None:
        self.widget().setPlainText(new_content)

    @property
    def modified_at(self) -> datetime.datetime:
        return self._modified_at

    @modified_at.setter
    def modified_at(self, new_create_datetime) -> None:
        self._modified_at = new_create_datetime
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
    def title(self) -> str:
        return self.widget().documentTitle()

    @title.setter
    def title(self, new_title: str) -> None:
        self.widget().setDocumentTitle(new_title)
        self.refresh_window_title()

    def refresh_window_title(self) -> None:
        self.setWindowTitle(
            self.title + '--' + self.modified_at.strftime('%c')
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


@dataclasses.dataclass
class SubWindowContent(phile.notify.File):
    sub_window: typing.Optional[NotificationMdiSubWindow] = None


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
        configuration = self._configuration
        # Keep track of sub-windows by title
        # so that we know which ones to modify when files are changed.
        self.sorter = sorter = (
            phile.data.SortedLoadCache[SubWindowContent](
                create_file=SubWindowContent,
                on_pop=self.on_pop,
                on_set=self.on_set,
                on_insert=self.on_insert,
            )
        )
        # Forward watchdog events into Qt signal and handle it there.
        self._notify_scheduler = scheduler = (
            phile.watchdog_extras.Scheduler(
                path_filter=functools.partial(
                    SubWindowContent.check_path,
                    configuration=configuration
                ),
                path_handler=phile.PySide2_extras.event_loop.CallSoon(
                    parent=self, call_target=sorter.update
                ),
                watched_path=configuration.notification_directory,
                watching_observer=watching_observer,
            )
        )
        # Make sure to remove handler from observer
        # when ``self`` is closed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(scheduler.unschedule)
        self._closed.connect(scheduler.unschedule)

    def set_up_trigger_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ) -> None:
        configuration = self._configuration
        # Take cooperative ownership of the directory
        # containing trigger file for trays.
        self._entry_point = entry_point = phile.trigger.EntryPoint(
            available_triggers={'close', 'show'},
            bind=True,
            callback_map={
                'close': lambda path: self.close(),
                'hide': lambda path: self.hide(),
                'show': lambda path: self.show(),
            },
            configuration=configuration,
            trigger_directory=pathlib.Path('phile-notify-gui'),
        )
        self.destroyed.connect(entry_point.unbind)
        # Forward watchdog events into Qt signal and handle it there.
        self._trigger_scheduler = scheduler = (
            phile.watchdog_extras.Scheduler(
                path_filter=entry_point.check_path,
                path_handler=phile.PySide2_extras.event_loop.CallSoon(
                    parent=self,
                    call_target=entry_point.activate_trigger
                ),
                watched_path=entry_point.trigger_directory,
                watching_observer=watching_observer,
            )
        )
        scheduler.schedule()
        # Make sure to remove handler from observer
        # when ``self`` is closed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(scheduler.unschedule)
        self._closed.connect(scheduler.unschedule)

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
        self.sorter.refresh(
            data_directory=configuration.notification_directory,
            data_file_suffix=configuration.notification_suffix
        )
        self._entry_point.remove_trigger('show')
        self._entry_point.add_trigger('hide')

    def on_pop(
        self, _index: int, content: SubWindowContent,
        _tracked_data: typing.List[SubWindowContent]
    ) -> None:
        sub_window = content.sub_window
        assert sub_window is not None
        sub_window.deleteLater()

    def on_set(
        self, _index: int, content: SubWindowContent,
        _tracked_data: typing.List[SubWindowContent]
    ) -> None:
        sub_window = content.sub_window
        assert sub_window is not None
        for key, value in self.get_data(content).items():
            setattr(sub_window, key, value)

    def on_insert(
        self, _index: int, content: SubWindowContent,
        _tracked_data: typing.List[SubWindowContent]
    ) -> None:
        new_data = self.get_data(content)
        sub_window = content.sub_window = (
            self.centralWidget().add_notification(**new_data)
        )
        sub_window.show()
        sub_window.closed.connect(self.on_notification_sub_window_closed)

    def get_data(self, content=SubWindowContent) -> dict:
        return {
            "content": content.text,
            "modified_at": content.modified_at,
            "title": content.title,
        }

    def on_notification_sub_window_closed(
        self, notification_title: str
    ) -> None:
        notification = phile.notify.File.from_path_stem(
            notification_title, configuration=self._configuration
        )
        notification.path.unlink(missing_ok=True)


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
