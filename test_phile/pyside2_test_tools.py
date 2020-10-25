#!/usr/bin/env python3
"""
----------------------
test_phile.PySide2.QtWidgts
----------------------
"""

# Standard libraries.
import datetime
import logging
import os
import pathlib
import tempfile
import typing

# External dependencies.
import PySide2.QtCore
from PySide2.QtGui import QIcon
import PySide2.QtWidgets

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class EnvironBackup:

    def __init__(self, *args, **kwargs) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._source_dict = os.environ
        self._backup_dict: typing.Dict[str, typing.Optional[str]] = {}

    def restore(self) -> None:
        source_dict = self._source_dict
        for key, value in self._backup_dict.items():
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value

    def backup_and_set(self, **kwargs) -> None:
        backup_dict = self._backup_dict
        source_dict = self._source_dict
        for key, value in kwargs.items():
            backup_dict[key] = source_dict.get(key)
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value


def q_icon_from_specified_theme(name: str, theme_name: str) -> QIcon:
    """
    Create an icon based on the given `name` only in the given theme.

    See: :func:`q_icon_from_theme`.
    """

    _logger.debug(
        'Fetching theme icon with name: %s from theme %s.', name,
        theme_name
    )
    for theme_search_path in QIcon.themeSearchPaths():
        theme_directory = pathlib.Path(theme_search_path) / theme_name
        icon_search_pattern = name + '.png'
        possible_icons = sorted(
            theme_directory.rglob(icon_search_pattern)
        )
        for icon_path in possible_icons:
            current_icon = QIcon(str(icon_path))
            if not current_icon.isNull():
                current_icon.name = lambda: name  # type: ignore
                return current_icon
    return QIcon()


def q_icon_from_theme(name: str) -> QIcon:
    """
    Create an icon based on the given name in the current theme.

    The `offscreen` Qt platform does not seem to implement icon themes.
    This function makes a minimal attempt to find an icon
    based on the specification found in
    https://specifications.freedesktop.org/icon-theme-spec
    but most of it is not implemented.
    This does not try to find a best match,
    nor parse the `index.theme`.
    nor does it fallback to parent themes.
    """
    _logger.debug('Fetching theme icon with name: %s.', name)
    theme_names_to_try = [
        QIcon.themeName(),
        'hicolor',
        QIcon.fallbackThemeName(),
    ]
    theme_names_to_try = [
        theme_name for theme_name in theme_names_to_try if theme_name
    ]
    for theme_name in theme_names_to_try:
        current_icon = q_icon_from_specified_theme(name, theme_name)
        if not current_icon.isNull():
            return current_icon
    return QIcon()


class SystemTrayIcon(PySide2.QtWidgets.QSystemTrayIcon):
    """
    A wrapper of QSystemTrayIcon that pretends to set an icon.

    The `offscreen` Qt platform does not have a system tray for icons.
    This class remembers the icon last set
    to mimic the system tray icon being set.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.__icon_ = super().icon()
        """The last icon set."""

        # If `QSystemTrayIcon` was able to set the icon, we use it.`
        # But if it was not, but an icon was given,
        # then we pretend to use the given icon.
        if self.__icon_ is None:
            if isinstance(args[0], QIcon):
                self.__icon_ = args[0]

    def icon(self) -> QIcon:
        """Returns the last icon set to be used in the system tray."""
        return self.__icon_

    def setIcon(self, new_icon: QIcon) -> None:
        """Sets the icon to be used in the system tray."""
        super().setIcon(new_icon)
        self.__icon_ = super().icon()
        if self.__icon_ != new_icon:
            self.__icon_ = new_icon


class QTestApplication(PySide2.QtWidgets.QApplication):

    def __init__(
        self,
        *args,
        process_event_wait_time: datetime.timedelta = datetime.timedelta(
            seconds=2
        ),
        qt_qpa_platform: typing.Optional[str] = 'offscreen',
        use_temporary_xdg_runtime_dir: bool = True,
        **kwargs
    ) -> None:
        self.__process_event_wait_time_ = process_event_wait_time
        environ_backup = EnvironBackup()
        self.__xdg_runtime_dir_ = None
        if use_temporary_xdg_runtime_dir:
            self.__xdg_runtime_dir_ = tempfile.TemporaryDirectory()
            environ_backup.backup_and_set(
                XDG_RUNTIME_DIR=self.__xdg_runtime_dir_.name
            )
        if qt_qpa_platform is not None:
            environ_backup.backup_and_set(
                QT_QPA_PLATFORM=qt_qpa_platform
            )
        self.__environ_backup_ = environ_backup
        super().__init__(*args, **kwargs)

    def __del__(self) -> None:
        if self.__xdg_runtime_dir_ is not None:
            self.__xdg_runtime_dir_.cleanup()
        self.__environ_backup_.restore()

    def process_deferred_delete_events(self) -> None:
        # Calling `processEvents`
        # does not process `DeferredDelete` events.
        # Asking `sendPostedEvents` to process all events
        # (which done by`processEvents`, I think)
        # also does not process it.
        # So this needs to be explicitly called.
        self.__class__.sendPostedEvents(
            None, PySide2.QtCore.QEvent.DeferredDelete
        )

    def process_events(self) -> None:
        self.__class__.processEvents(
            PySide2.QtCore.QEventLoop.AllEvents,
            int(
                self.__process_event_wait_time_ /
                datetime.timedelta(milliseconds=1)
            )
        )

    def tear_down(self) -> None:
        # Destructor clean-up process.
        # While it would be great to have this in `__del__`,
        # Python3 does not guarantee when the finaliser is called.
        # So we have an explicit clean-up method here instead.
        self.process_events()
        self.process_deferred_delete_events()
        self.shutdown()
