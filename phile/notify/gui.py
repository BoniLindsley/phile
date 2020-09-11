#!/usr/bin/env python3

# Standard library.
import datetime
import logging

# External dependencies.
from PySide2.QtCore import Qt
from PySide2.QtCore import Signal, Slot  # type: ignore
from PySide2.QtGui import (
    QCloseEvent, QHideEvent, QResizeEvent, QShowEvent, QPalette
)
from PySide2.QtWidgets import QMdiArea, QMdiSubWindow, QTextEdit

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class NotificationMdiSubWindow(QMdiSubWindow):

    hidden = Signal()
    shown = Signal()

    def __init__(
        self, *, name: str, creation_datetime: datetime.datetime,
        content: str
    ):
        super().__init__()
        self._is_read = False
        content_widget = QTextEdit()
        content_widget.setPlainText(content)
        content_widget.setReadOnly(True)
        self.setWidget(content_widget)
        # Set the size now so that parent QMdiArea
        # can use it to position sub-windows in resize events.
        self.adjustSize()
        self.mark_as_read(self._is_read)
        # By default, clicking the close window button hides it.
        # This makes sure it gets "closed" properly.
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(
            name + '--' + creation_datetime.strftime('%c')
        )

    def closeEvent(self, close_event: QCloseEvent):
        _logger.debug('Sub-window closed.')
        # The default close event also hides the widget.
        # But it first gives controls back to C++ code.
        # That means re-tiling would not happen
        # until the Python interpreter gains control again.
        # In particular, the `hideEvent` might not occur for a while.
        # So explicitly hide it here to trigger re-tiling immediately.
        self.hide()
        super().closeEvent(close_event)

    def hideEvent(self, hide_event: QHideEvent):
        # When a sub-window is hidden, a re-tile is necessary
        # to fill any gaps left by the hidden widget.
        # It is possible to hide without closing a widget.
        # So we need to handle the hide event explicitly.
        _logger.debug('Sub-window hidden.')
        self.hidden.emit()  # type: ignore
        super().hideEvent(hide_event)

    def is_marked_as_read(self) -> bool:
        return self._is_read

    def mark_as_read(self, is_read: bool):
        self._is_read = is_read
        content_widget = self.widget()
        content_palette = content_widget.palette()
        base_color = content_palette.color(QPalette.Window)
        text_color = content_palette.color(
            QPalette.Disabled if is_read else QPalette.Active,
            QPalette.WindowText
        )
        content_palette.setColor(QPalette.Text, text_color)
        content_palette.setColor(QPalette.Base, base_color)
        content_widget.setPalette(content_palette)

    def showEvent(self, show_event: QShowEvent):
        # Showing a widget typically also activates it by default.
        # So handling activation event (or window state change events)
        # might seem sufficient.
        # However, it is possible to show a widget without activating it.
        # So we need to handle show events explicitly.
        # We need to make sure that showing a sub-window would re-tile
        # so it goes into the correct position.
        _logger.debug('Sub-window shown.')
        self.shown.emit()  # type: ignore
        super().showEvent(show_event)


class NotificationMdi(QMdiArea):

    def __init__(self, *args, **kwargs):
        _logger.debug('Creating notification MDI.')
        super().__init__(*args, **kwargs)
        self.setActivationOrder(QMdiArea.CreationOrder)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def addSubWindow(self, *args, **kwargs) -> QMdiSubWindow:
        _logger.debug(
            'Adding sub-window. Total will be %s.',
            len(self.subWindowList()) + 1
        )
        new_sub_window = super().addSubWindow(*args, **kwargs)
        new_sub_window.hidden.connect(self._tile_sub_windows_vertically)
        new_sub_window.shown.connect(self._tile_sub_windows_vertically)
        new_sub_window.windowStateChanged.connect(
            self._retile_on_sub_window_state_changed
        )
        return new_sub_window

    @Slot(Qt.WindowState, Qt.WindowState)  # type: ignore
    def _retile_on_sub_window_state_changed(self, old_state, new_state):
        # States including minimising, maximising, fullscreen and active.
        # Only the first two are handled.
        #
        # Windows can switch between active and inactive
        # without needing repositioning.
        # So that is ignored.
        #
        # Not sure what fullscreen would mean for a sub-window..?
        _logger.debug('Sub-window state changed.')
        min_max_state = Qt.WindowMaximized | Qt.WindowMinimized
        old_min_max_state = old_state & min_max_state
        new_min_max_state = new_state & min_max_state
        if old_min_max_state != new_min_max_state:
            self._tile_sub_windows_vertically()
        else:
            _logger.debug('MDI sub-window min-max state unchanged.')

    def resizeEvent(self, resize_event: QResizeEvent):
        _logger.debug('Resized.')
        self._tile_sub_windows_vertically(area_size=resize_event.size())
        super().resizeEvent(resize_event)

    def showEvent(self, show_event: QShowEvent):
        _logger.debug('Shown.')
        self._tile_sub_windows_vertically()
        super().showEvent(show_event)

    @Slot()  # type: ignore
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
