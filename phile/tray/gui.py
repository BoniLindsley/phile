#!/usr/bin/env python3

# Standard library.
import bisect
import json
import logging
import os
import pathlib
import pkg_resources
import sys
import typing

# External dependencies.
from PySide2.QtCore import QObject
from PySide2.QtCore import Slot  # type: ignore
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QSystemTrayIcon, QWidget
import watchdog.events  # type: ignore

# Internal packages.
from phile.PySide2_extras.watchdog_wrapper import (
    FileSystemMonitor, FileSystemSignalEmitter, Observer
)
import phile.notify.notification
from phile.notify.notification import _app_dir_paths

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class Configuration(phile.notify.notification.Configuration):

    def __init__(
        self,
        *args,
        tray_directory: pathlib.Path = _app_dir_paths.user_state /
        "tray",
        tray_icon_name: str = 'phile-tray-empty',
        tray_suffix: str = '.tray',
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tray_directory = tray_directory
        self.tray_icon_name = tray_icon_name
        self.tray_suffix = tray_suffix


class TrayFile:

    class ParentError(ValueError):
        pass

    class SuffixError(ValueError):
        pass

    def __init__(
        self,
        *,
        configuration: Configuration = None,
        name: str = None,
        path: pathlib.Path = None
    ) -> None:
        if path is None:
            if configuration is None or name is None:
                raise ValueError(
                    'TrayFile is constructed from path'
                    ' or from both configuration and name'
                )
            path = configuration.tray_directory / (
                name + configuration.tray_suffix
            )
        else:
            if configuration is not None:
                path_parent = path.parent
                directory = configuration.tray_directory
                if path_parent != directory:
                    raise TrayFile.ParentError(
                        'Path parent ({}) is not {}'.format(
                            path_parent, directory
                        )
                    )
                path_suffix = path.suffix
                tray_suffix = configuration.tray_suffix
                if path_suffix != tray_suffix:
                    raise TrayFile.SuffixError(
                        'Path suffix ({}) is not {}'.format(
                            path_suffix, tray_suffix
                        )
                    )
        self.path = path

        self.icon_name: typing.Optional[str] = None
        self.icon_path: typing.Optional[pathlib.Path] = None
        self.text_icon: typing.Optional[str] = None

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.path == other.path

    def __lt__(self, other):
        return self.path < other.path

    @property
    def name(self) -> str:
        return self.path.stem

    def load(self):
        """
        Parse tray file for a tray icon to be displayed.

        The input file should start with a single line
        that can be displayed in a text tray environment such as `tmux`.

        The remaining lines should describe the request in json format.
        It should contain the following keys:

        * `icon_path` or `icon_name`: The latter is searched for
          from the underlying theme setup.

        It should not contan any other keys,
        and may be ignored, subject to implementation details.
        """

        with self.path.open() as file_stream:

            self.text_icon = file_stream.readline().rstrip('\r\n')
            _logger.debug("Using text icon: %s", self.text_icon)

            # Make sure there are content to read by reading one byte
            # and then resetting the offset before decoding.
            current_offset = file_stream.tell()
            if file_stream.read(1):
                file_stream.seek(current_offset)
                json_content = json.load(file_stream)
            else:
                json_content = {}

            self.icon_name = json_content.get('icon_name')
            _logger.debug("Using icon name: %s", self.icon_name)
            icon_path = json_content.get('icon_path')
            if icon_path is not None:
                self.icon_path = pathlib.Path(icon_path)
            else:
                self.icon_path = None
            _logger.debug("Using icon path: %s", self.icon_path)

    def remove(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def save(self):
        with self.path.open('w+') as file_stream:
            if self.text_icon is not None:
                file_stream.write(self.text_icon)
            # End with a new line
            # so that appending would not jumble up the text.
            json_content: typing.Dict[str, str] = {}
            for key in ['icon_name', 'icon_path']:
                value = getattr(self, key, None)
                if value is not None:
                    json_content[key] = str(value)
            if json_content:
                file_stream.write('\n')
                json.dump(json_content, file_stream)


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

    def __init__(
        self,
        *args,
        configuration: Configuration = None,
        observer: Observer = None,
        **kwargs
    ) -> None:

        #if not QSystemTrayIcon.isSystemTrayAvailable():
        #    raise RuntimeError(
        #        "Tray icon support not found on the current system."
        #    )

        super().__init__(*args, **kwargs)
        # Keep track of GUI icons created.
        self.tray_files: typing.List[TrayFile] = []
        # Attach a file monitor to it as a child
        # for automatic life-time management.
        if observer is None:
            observer = Observer()
        self._file_system_monitor = FileSystemMonitor(
            self, _watchdog_observer=observer
        )
        # Figure out where tray files are and their suffix.
        if configuration is None:
            configuration = Configuration()
        self._configuration = configuration
        # Let the file monitor know which directory we are interested in.
        self._signal_emitter = FileSystemSignalEmitter(
            monitored_path=self._configuration.tray_directory,
            parent=self._file_system_monitor,
        )
        signal = self._signal_emitter.file_system_event_detected
        signal.connect(  # type: ignore
            self.on_file_system_event_detected
        )

    def hide(self):
        self._signal_emitter.stop()
        for tray_icon in self.tray_children():
            tray_icon.hide()

    def show(self):
        # Update all existing tray files.
        configuration = self._configuration
        tray_directory = configuration.tray_directory
        for tray_file_path in tray_directory.iterdir():
            if tray_file_path.is_file():
                self.on_file_system_event_detected(
                    watchdog.events.FileCreatedEvent(tray_file_path)
                )
        for tray_icon in self.tray_children():
            tray_icon.show()
        if not self._file_system_monitor.was_start_called():
            self._file_system_monitor.start()
        self._signal_emitter.start()

    @Slot(watchdog.events.FileSystemEvent)  # type: ignore
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
            _logger.debug('Watchdog event: tray file moved.')
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
        # Only files of a specific extension is a tray file.
        try:
            tray_file = TrayFile(
                configuration=self._configuration,
                path=pathlib.Path(watchdog_event.src_path)
            )
        except TrayFile.SuffixError as error:
            _logger.debug('Watchdog event: %s', error)
            return
        # Determine what to do base on existence of the actual file.
        # There might be a delay between the file operation
        # and the event being received here.
        self.load(tray_file)

    def load(self, tray_file: TrayFile) -> None:
        # Figure out the position of the tray icon is in
        # in the tracked tray icons, if it is tracked at all.
        index = bisect.bisect_left(self.tray_files, tray_file)
        try:
            is_tracked = self.tray_files[index] == tray_file
        except IndexError:
            is_tracked = False
        if is_tracked:
            _logger.debug(
                "Loading tray file in position %s of %s.", index + 1,
                len(self.tray_files)
            )
        else:
            _logger.debug("Loading tray file that was untracked.")
        # Try to load the tray file.
        tray_file_exists = True
        try:
            tray_file.load()
        except FileNotFoundError:
            tray_file_exists = False
        # If the tray file does not exist,
        # either remove the tray icon or there is nothing to do.
        if not tray_file_exists:
            if not is_tracked:
                _logger.debug(
                    "Tray file does not exist nor tracked."
                    " Nothing to do."
                )
                return
            else:
                self.remove(index)
                return
        # Can assume from here that the tray file is loaded.
        if is_tracked:
            self.set(index, tray_file)
        else:
            self.insert(index, tray_file)

    def insert(self, index: int, tray_file: TrayFile) -> None:
        # Create an additional icon to be displayed,
        # and shift all the icons.
        # Assuming icons are displayed in the order they were created,
        # the icons displayed need to be reordered ourselves.
        #
        # Add a new tray icon.
        #
        # Children = [ O 1 2 3 4 5 6 ]
        #    becomes [ O 1 2 3 4 5 6 7 ]
        self.tray_files.insert(index, tray_file)
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

    def set(self, index: int, tray_file: TrayFile) -> None:
        _logger.debug(
            "Setting tray file in position %s of %s", index + 1,
            len(self.tray_files)
        )
        new_icon = self.load_icon(tray_file)
        children = self.tray_children()
        children[index].setIcon(new_icon)
        self.tray_files[index] = tray_file

    def remove(self, index: int) -> None:
        _logger.debug(
            "Removing tray icon in position %s of %s", index + 1,
            len(self.tray_files)
        )
        # Using `deleteLater` directly
        # does not remove from the list immeidately.
        # But we need the children list to be changed immediately
        # so it stay in sync with the list of tray files.
        children = self.tray_children()
        tray_icon_to_delete = children.pop(index)
        fake_parent = QObject()
        tray_icon_to_delete.setParent(fake_parent)
        fake_parent.deleteLater()
        self.tray_files.pop(index)

    def load_icon(self, tray_file: TrayFile) -> QIcon:
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
    try:
        gui_icon_list = GuiIconList()
    except RuntimeError as e:
        _logger.critical('Unable to create tray icons: %s', e)
        return 1
    gui_icon_list.show()
    return app.exec_()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
