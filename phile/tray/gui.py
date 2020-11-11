#!/usr/bin/env python3
"""
--------
Tray GUI
--------
"""

# Standard library.
import bisect
import io
import json
import logging
import os
import pathlib
import pkg_resources
import shutil
import signal
import sys
import typing
import warnings

# External dependencies.
from PySide2.QtCore import QObject
from PySide2.QtCore import Signal, SignalInstance
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QSystemTrayIcon, QWidget
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.PySide2_extras.posix_signal
import phile.PySide2_extras.watchdog_wrapper
import phile.tray
import phile.tray.event
import phile.trigger
import phile.watchdog_extras

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


def set_icon_paths() -> None:
    """Tell PySide2 where to find icons."""

    # Users can define their own themes to use.
    # But if the theme does not contain a required icon,
    # it can be searched for in a fallback theme.
    fallback_theme_name = "blank"
    QIcon.setFallbackThemeName(fallback_theme_name)

    # Themes are directories inside some base directories.
    # Tell Qt where these base directories may be.
    # In particular, add resources from this package.
    theme_search_paths = QIcon.themeSearchPaths()
    resource_dir_path = pkg_resources.resource_filename(
        __name__, "resources"
    )
    resource_theme_path = os.path.join(resource_dir_path, "icons")
    if resource_theme_path not in theme_search_paths:
        theme_search_paths.append(resource_theme_path)
        QIcon.setThemeSearchPaths(theme_search_paths)

    # Whenever a required icon does not exist in the user theme,
    #   and also not in the fallback theme,
    #   then search for it as a file in the fallback path.
    # Try the `pixmaps` directory inside the resource directory.
    fallback_search_paths = QIcon.fallbackSearchPaths()
    resource_pixmaps_path = os.path.join(resource_dir_path, "pixmaps")
    if resource_pixmaps_path not in fallback_search_paths:
        fallback_search_paths.append(resource_pixmaps_path)
        QIcon.setFallbackSearchPaths(fallback_search_paths)


class GuiIconList(QObject):

    _closed = typing.cast(SignalInstance, Signal())
    """
    Internal. Emitted when the list is closed.

    Used for cleaning up internal resources.
    """

    def __init__(
        self, *args, configuration: phile.configuration.Configuration,
        watching_observer: watchdog.observers.Observer, **kwargs
    ) -> None:
        """
        :param watching_observer:
            The :attr:`~watchdog.observers.Observer` instance to use
            to monitor for tray icon changes.
            It is up to the caller to ensure the given ``watching_observer``
            is :meth:`~watchdog.observers.api.BaseObserver.start`-ed
            and not :meth:`~watchdog.observers.api.BaseObserver.stop`-ped
            as appropriate.
            If :data:`None`, a daemon instance is created
            and :meth:`~watchdog.observers.api.BaseObserver.start`-ed,
            and :meth:`~watchdog.observers.api.BaseObserver.stop`-ped
            and :meth:`~watchdog.observers.api.BaseObserver.join`-ped
            when ``self``
            is `~PySide2.QtCore.QObject.QtCore.QObject.deleteLater`.
        :type watching_observer:
            :attr:`~watchdog.observers.Observer` or :data:`None`
        """
        # Create as QObject first to use its methods.
        super().__init__(*args, **kwargs)
        # Figure out where tray files are and their suffix.
        self._configuration = configuration
        # Set up tray directory monitoring.
        self._set_up_tray_event_handler(
            watching_observer=watching_observer
        )
        self._set_up_trigger_event_handler(
            watching_observer=watching_observer
        )

    def _set_up_tray_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ):
        self._tray_sorter = phile.tray.event.Sorter(
            configuration=self._configuration,
            insert=self.insert,
            pop=(lambda index, tray_file: self.remove(index)),
            set_item=self.set,
        )
        # Convert events to tray files.
        # It does not matter whether the event say a file is changed
        # or it has been deleted.
        # It may have been changed again between the event being emitted
        # and the event being processed.
        # So we get the tray file out of the event
        # and process based on the file instead of the event.
        event_converter = phile.tray.event.Converter(
            configuration=self._configuration,
            tray_handler=self._tray_sorter
        )
        # Forward watchdog events into Qt signal and handle it there.
        signal_emitter = (
            phile.PySide2_extras.watchdog_wrapper.SignalEmitter(
                parent=self,
                event_handler=event_converter,
            )
        )
        # Figure out whether an event is relevant before giving it to Qt.
        event_filter = phile.tray.event.Filter(
            configuration=self._configuration,
            event_handler=signal_emitter
        )
        # Use a scheduler to toggle the event handling on and off.
        dispatcher = phile.watchdog_extras.Dispatcher(
            event_handler=event_filter
        )
        watched_path = self._configuration.tray_directory
        watched_path.mkdir(exist_ok=True, parents=True)
        self._tray_scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=dispatcher,
            watched_path=watched_path,
            watching_observer=watching_observer,
        )
        # Make sure to remove handler from observer
        # when ``self`` is destroyed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(self._tray_scheduler.unschedule)
        self._closed.connect(self._tray_scheduler.unschedule)

    def _set_up_trigger_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ) -> None:
        # Take cooperative ownership of the directory
        # containing trigger file for trays.
        self._entry_point = phile.trigger.EntryPoint(
            configuration=self._configuration,
            trigger_directory=pathlib.Path('phile-tray-gui'),
        )
        self._entry_point.bind()
        self.destroyed.connect(self._entry_point.unbind)
        # Turn file system events into trigger names to process.
        event_conveter = phile.trigger.EventConverter(
            configuration=self._configuration,
            trigger_handler=self.process_trigger,
        )
        # Forward watchdog events into Qt signal and handle it there.
        signal_emitter = (
            phile.PySide2_extras.watchdog_wrapper.SignalEmitter(
                parent=self,
                event_handler=event_conveter,
            )
        )
        # Filter out non-trigger activation events
        # to reduce cross-thread communications.
        event_filter = phile.trigger.EventFilter(
            configuration=self._configuration,
            event_handler=signal_emitter,
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
        # when ``self`` is destroyed
        # so the observer would not call non-existence handlers.
        self.destroyed.connect(self._trigger_scheduler.unschedule)
        self._closed.connect(self._trigger_scheduler.unschedule)
        # Allow closing with a trigger.
        self._entry_point.add_trigger('close')
        self._entry_point.add_trigger('show')

    def process_trigger(self, trigger_name: str) -> None:
        if trigger_name == 'hide':
            self.hide()
        elif trigger_name == 'show':
            self.show()
        elif trigger_name == 'close':
            self.close()
        else:
            _logger.warning('Unknown trigger command: %s', trigger_name)

    def close(self) -> None:
        """Tell the list the icons should not be displayed anymore."""
        self.hide()
        self._closed.emit()
        self.deleteLater()

    def hide(self) -> None:
        """Hide tray icons if not already hidden."""
        if self.is_hidden():
            return
        self._tray_scheduler.unschedule()
        self._tray_sorter.tray_files.clear()
        for tray_icon in self.tray_children():
            tray_icon.hide()
            tray_icon.deleteLater()
        self._entry_point.remove_trigger('hide')
        self._entry_point.add_trigger('show')

    def is_hidden(self) -> bool:
        """Returns whether the tray icon is hidden."""
        return not self._tray_scheduler.is_scheduled()

    def show(self) -> None:
        """Show tray icons if not already shown."""
        if not self.is_hidden():
            return
        # Start monitoring to not miss file events.
        self._tray_scheduler.schedule()
        # Update all existing tray files.
        self._tray_sorter.load_all()
        self._entry_point.remove_trigger('show')
        self._entry_point.add_trigger('hide')

    def insert(self, index: int, tray_file: phile.tray.File) -> None:
        # Create an additional icon to be displayed,
        # and shift all the icons.
        # Assuming icons are displayed in the order they were created,
        # the icons displayed need to be reordered ourselves.
        #
        # Add a new tray icon.
        #
        # Children = [ O 1 2 3 4 5 6 ]
        #    becomes [ O 1 2 3 4 5 6 7 ]
        last_icon = QSystemTrayIcon(self)
        children = self.tray_children()
        icon_count = len(children)
        _logger.debug(
            "Inserting tray file into position %s of %s", index + 1,
            icon_count
        )
        # Make icons on the right take the icon on the left.
        # Move 6 to 7, move 5 to 6, move 4 to 5, move 3 to 4.
        #           ^-- (icon_count - 1)     (index + 1) --^
        #
        # Children = [ O 1 2 3 4 5 6 7 ]
        #      index = 3     |--     ^--- No icon
        # icon_count = 8       V
        #            [ O 1 2 X 3 4 5 6 ]
        #
        # The icon at index is the position the new tray icon is at.
        for index_to_shift_to in range(icon_count - 1, index, -1):
            icon_to_the_left = children[index_to_shift_to - 1].icon()
            children[index_to_shift_to].setIcon(icon_to_the_left)
        # Fetch the icon image described by the icon request.
        new_icon = self.load_icon(tray_file)
        children[index].setIcon(new_icon)
        # Newly created icons are not displayed by default.
        # It is only displayed here,
        # after all the icons are set properly.
        last_icon.show()

    def set(self, index: int, tray_file: phile.tray.File) -> None:
        new_icon = self.load_icon(tray_file)
        children = self.tray_children()
        children[index].setIcon(new_icon)

    def remove(self, index: int) -> None:
        # Using `deleteLater` directly
        # does not remove from the list immeidately.
        # But we need the children list to be changed immediately
        # so it stay in sync with the list of tray files.
        children = self.tray_children()
        tray_icon_to_delete = children.pop(index)
        fake_parent = QObject()
        tray_icon_to_delete.setParent(fake_parent)
        fake_parent.deleteLater()

    def load_icon(self, tray_file: phile.tray.File) -> QIcon:
        """Load a GUI icon as described by `tray_file`."""
        # Path is more specific. Make it a priority.
        icon_path = tray_file.icon_path
        if icon_path is not None:
            _logger.debug('Loading tray icon from path.')
            return QIcon(str(icon_path))
        # Find an icon using the current theme.
        icon_name = tray_file.icon_name
        if icon_name is not None:
            _logger.debug('Loading tray icon from name.')
            return QIcon.fromTheme(icon_name)
        # Nothing was set. Use a default setting.
        # If it shuld be blank,
        # an invalid name could be specified instead.
        _logger.debug('Loading tray icon. Using default.')
        return QIcon.fromTheme(self._configuration.tray_icon_name)

    def tray_children(self) -> typing.List[QSystemTrayIcon]:
        return [
            child for child in self.children()
            if isinstance(child, QSystemTrayIcon)
        ]


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    app = QApplication(argv)
    # Let Qt know where to find icons.
    set_icon_paths()
    configuration = phile.configuration.Configuration()
    watching_observer = watchdog.observers.Observer()
    watching_observer.daemon = True
    watching_observer.start()
    try:
        gui_icon_list = GuiIconList(
            configuration=configuration,
            watching_observer=watching_observer
        )
    except RuntimeError as e:
        _logger.critical('Unable to create tray icons: %s', e)
        return 1
    gui_icon_list.show()
    gui_icon_list.destroyed.connect(app.quit)
    posix_signal = phile.PySide2_extras.posix_signal.PosixSignal(
        gui_icon_list
    )
    posix_signal.signal_received.connect(gui_icon_list.close)
    phile.PySide2_extras.posix_signal.install_noop_signal_handler(
        signal.SIGINT
    )
    return_value = app.exec_()
    watching_observer.stop()
    watching_observer.join()
    return return_value


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
