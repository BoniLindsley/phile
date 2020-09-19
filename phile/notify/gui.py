#!/usr/bin/env python3

# Standard library.
import datetime
import logging

# External dependencies.
from PySide2.QtCore import QEvent, Qt
from PySide2.QtCore import Signal  # type: ignore
from PySide2.QtGui import (
    QCloseEvent, QHideEvent, QResizeEvent, QShowEvent, QPalette
)
from PySide2.QtWidgets import QMdiArea, QMdiSubWindow, QTextEdit

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class NotificationMdiSubWindow(QMdiSubWindow):

    closed = Signal(str)
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
        self.closed.emit(self.name)  # type: ignore

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
