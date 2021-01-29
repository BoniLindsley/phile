#!/usr/bin/env python3

# Standard Libraries
import typing

# External dependencies.
import PySide2.QtGui
import PySide2.QtWidgets


class OffscreenSystemTrayIcon(PySide2.QtWidgets.QSystemTrayIcon):
    """
    A wrapper of QSystemTrayIcon that pretends to set an icon.

    The `offscreen` Qt platform does not have a system tray for icons.
    This class remembers the icon last set
    to mimic the system tray icon being set.
    """

    # This class tries to forward everything to the base class.
    # And only fallback to internal book-keeping if that fails.
    # So enforcing coverage might not make much sense.
    # If this needs to be relied upon, coverage can be enabled again.

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)

        self.__icon = super().icon()
        """The last icon set."""

        # If `QSystemTrayIcon` was able to set the icon, we use it.`
        # But if it was not, but an icon was given,
        # then we pretend to use the given icon.
        if self.__icon is None:  # pragma: no cover
            if isinstance(args[0], PySide2.QtGui.QIcon):
                self.__icon = args[0]

    def icon(self) -> PySide2.QtGui.QIcon:
        """Returns the last icon set to be used in the system tray."""
        return self.__icon

    def setIcon(self, new_icon: PySide2.QtGui.QIcon) -> None:
        """Sets the icon to be used in the system tray."""
        super().setIcon(new_icon)
        self.__icon = super().icon()
        if self.__icon != new_icon:  # pragma: no cover
            self.__icon = new_icon
