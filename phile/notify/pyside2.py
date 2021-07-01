#!/usr/bin/env python3

# TODO(BoniLindsley): Rewrite. Mdi is probably not the right tool.

# Standard library.
import asyncio
import collections.abc
import datetime
import functools
import logging
import signal
import sys
import typing

# External dependencies.
import PySide2.QtCore
import PySide2.QtWidgets

# Internal packages.
import phile.PySide2.QtCore
import phile.PySide2.QtNetwork
import phile.data
import phile.main
import phile.notify
import phile.signal
import phile.trigger
import phile.trigger.pyside2

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)
"""Logger whose name is the module name."""


class NotificationMdiSubWindow(PySide2.QtWidgets.QMdiSubWindow):

    closed = typing.cast(
        PySide2.QtCore.SignalInstance, PySide2.QtCore.Signal(str)
    )
    """Emitted when the sub-window is closed."""

    def __init__(self, *, notify_entry: phile.notify.Entry):
        super().__init__()
        content_widget = PySide2.QtWidgets.QTextEdit()
        content_widget.setReadOnly(True)
        self.setWidget(content_widget)
        # Set the size now so that parent QMdiArea
        # can use it to position sub-windows in resize events.
        self.adjustSize()
        # By default, clicking the close window button hides it.
        # This makes sure it gets "closed" properly.
        self.setAttribute(PySide2.QtCore.Qt.WA_DeleteOnClose)
        self.update_to_entry(notify_entry=notify_entry)
        self.is_read = False

    def changeEvent(self, change_event: PySide2.QtCore.QEvent) -> None:
        super().changeEvent(change_event)
        event_type = change_event.type()
        if event_type != PySide2.QtCore.QEvent.WindowStateChange:
            return
        # States: minimised, maximised, fullscreen and active.
        # Only the first two are handled.
        #
        # Windows can switch between active and inactive
        # without needing repositioning.
        # So that is ignored.
        #
        # Not sure what fullscreen would mean for a sub-window..?
        min_max_state = (
            PySide2.QtCore.Qt.WindowMaximized
            | PySide2.QtCore.Qt.WindowMinimized
        )
        old_min_max_state = change_event.oldState() & min_max_state
        new_min_max_state = self.windowState() & min_max_state
        if old_min_max_state == new_min_max_state:
            _logger.debug('Sub-window not min-maxiimized.')
            return
        _logger.debug('Sub-window min-maximized: re-tiling parent.')
        self._retile_parent()

    def closeEvent(self, close_event: PySide2.QtGui.QCloseEvent) -> None:
        """Internal method to handle the sub-window being closed. """
        del close_event
        self.closed.emit(self.title)

    def update_to_entry(self, notify_entry: phile.notify.Entry) -> None:
        modified_at = notify_entry.modified_at
        if modified_at is None:
            modified_at = datetime.datetime.now()
        self._modified_at = modified_at
        self.title = notify_entry.name
        self.content = notify_entry.text
        self.refresh_window_title()

    @property
    def content(self) -> str:
        return typing.cast(str, self.widget().toPlainText())

    @content.setter
    def content(self, new_content: str) -> None:
        self.widget().setPlainText(new_content)

    def hideEvent(self, hide_event: PySide2.QtGui.QHideEvent) -> None:
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
        QPalette = PySide2.QtGui.QPalette
        content_widget = self.widget()
        content_palette = content_widget.palette()
        text_color = content_palette.color(QPalette.Text)
        disabled_text_color = content_palette.color(
            QPalette.Disabled, QPalette.WindowText
        )
        return text_color == disabled_text_color

    @is_read.setter
    def is_read(self, new_is_read: bool) -> None:
        QPalette = PySide2.QtGui.QPalette
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
        return typing.cast(str, self.widget().documentTitle())

    @title.setter
    def title(self, new_title: str) -> None:
        self.widget().setDocumentTitle(new_title)
        self.refresh_window_title()

    def refresh_window_title(self) -> None:
        self.setWindowTitle(
            self.title + '--' + self._modified_at.strftime('%c')
        )

    def _retile_parent(self) -> None:
        mdi_area = self.mdiArea()
        if mdi_area is not None:
            mdi_area._tile_sub_windows_vertically()

    def showEvent(self, show_event: PySide2.QtGui.QShowEvent) -> None:
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


class NotificationMdi(PySide2.QtWidgets.QMdiArea):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        _logger.debug('Creating notification MDI.')
        super().__init__(*args, **kwargs)
        self.setActivationOrder(PySide2.QtWidgets.QMdiArea.CreationOrder)
        self.setHorizontalScrollBarPolicy(
            PySide2.QtCore.Qt.ScrollBarAsNeeded
        )
        self.setVerticalScrollBarPolicy(
            PySide2.QtCore.Qt.ScrollBarAsNeeded
        )

    def add_notification(
        self, notify_entry: phile.notify.Entry
    ) -> NotificationMdiSubWindow:
        _logger.debug(
            'Adding notification sub-window. Total will be %s.',
            len(self.subWindowList()) + 1
        )
        notification_mdi_sub_window = NotificationMdiSubWindow(
            notify_entry=notify_entry
        )
        sub_window = super().addSubWindow(notification_mdi_sub_window)
        assert sub_window is notification_mdi_sub_window
        return notification_mdi_sub_window

    def resizeEvent(
        self, resize_event: PySide2.QtGui.QResizeEvent
    ) -> None:
        _logger.debug('Resized: default handling.')
        super().resizeEvent(resize_event)
        _logger.debug('Resized: re-tiling.')
        self._tile_sub_windows_vertically(area_size=resize_event.size())

    def showEvent(self, show_event: PySide2.QtGui.QShowEvent) -> None:
        _logger.debug('Shown: default handling.')
        super().showEvent(show_event)
        _logger.debug('Shown: re-tiling.')
        self._tile_sub_windows_vertically()

    def _tile_sub_windows_vertically(
        self,
        *,
        area_size: typing.Optional[PySide2.QtCore.QSize] = None
    ) -> None:
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
        if self.viewMode() != PySide2.QtWidgets.QMdiArea.SubWindowView:
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


class MainWindow(
    phile.trigger.pyside2.TriggerControlled,
    PySide2.QtWidgets.QMainWindow,
):

    def __init__(
        self,
        *args: typing.Any,
        loop: asyncio.AbstractEventLoop,
        notify_registry: phile.notify.Registry,
        pyside2_executor: phile.PySide2.QtCore.Executor,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ):
        # Create the window.
        super().__init__(
            *args,
            pyside2_executor=pyside2_executor,
            trigger_prefix=_loader_name,
            trigger_registry=trigger_registry,
            **kwargs,
        )
        self._notify_mdi_sub_windows: (
            dict[str, NotificationMdiSubWindow]
        ) = {}
        self._loop = loop
        self._notify_registry = notify_registry
        self.setAttribute(PySide2.QtCore.Qt.WA_DeleteOnClose)
        # Create the GUI for displaying notifications.
        self._mdi_area = mdi_area = NotificationMdi()
        self.setCentralWidget(mdi_area)

    def update_entries(
        self,
        notify_entries: collections.abc.Iterable[phile.notify.Entry],
    ) -> None:
        for notify_entry in notify_entries:
            self.set_entry(notify_entry)

    def discard_entry(self, notify_entry: phile.notify.Entry) -> None:
        try:
            sub_window = (
                self._notify_mdi_sub_windows.pop(notify_entry.name)
            )
        except KeyError:
            return
        sub_window.deleteLater()

    def set_entry(self, notify_entry: phile.notify.Entry) -> None:
        try:
            sub_window = (
                self._notify_mdi_sub_windows[notify_entry.name]
            )
        except KeyError:
            sub_window = (
                self._notify_mdi_sub_windows[notify_entry.name]
            ) = self._mdi_area.add_notification(notify_entry)
            sub_window.closed.connect(
                functools.partial(
                    self._loop.call_soon_threadsafe,
                    self._notify_registry.discard,
                )
            )
            sub_window.show()
        sub_window.update_to_entry(notify_entry)


async def run(
    *,
    notify_registry: phile.notify.Registry,
    trigger_registry: phile.trigger.Registry,
    pyside2_executor: phile.PySide2.QtCore.Executor,
) -> None:  # pragma: no cover
    loop = asyncio.get_running_loop()
    window_closed = asyncio.Event()
    window = await asyncio.wrap_future(
        pyside2_executor.submit(
            MainWindow,
            loop=loop,
            notify_registry=notify_registry,
            pyside2_executor=pyside2_executor,
            trigger_registry=trigger_registry,
        )
    )
    try:
        posix_signal = await asyncio.wrap_future(
            pyside2_executor.submit(
                phile.PySide2.QtNetwork.PosixSignal, window
            )
        )

        def set_closed_event(
            qobject: typing.Optional[PySide2.QtCore.QObject] = None,
        ) -> None:
            del qobject
            loop.call_soon_threadsafe(window_closed.set)

        def on_start() -> None:
            window.destroyed.connect(set_closed_event)
            window.setAttribute(PySide2.QtCore.Qt.WA_DeleteOnClose)
            window.show()
            posix_signal.signal_received.connect(window.close)
            phile.signal.install_noop_signal_handler(signal.SIGINT)

        await asyncio.wrap_future(pyside2_executor.submit(on_start))
        notify_view = notify_registry.event_queue.__aiter__()
        await asyncio.wrap_future(
            pyside2_executor.submit(
                window.update_entries,
                notify_registry.current_values.copy(),
            )
        )

        async def propagate_notify_events() -> None:
            async for notify_event in notify_view:
                if (
                    notify_event.type == phile.data.EventType.INSERT
                    or notify_event.type == phile.data.EventType.SET
                ):
                    await asyncio.wrap_future(
                        pyside2_executor.submit(
                            window.set_entry,
                            notify_event.value,
                        )
                    )
                else:
                    await asyncio.wrap_future(
                        pyside2_executor.submit(
                            window.discard_entry,
                            notify_event.value,
                        )
                    )

        propagating_task = asyncio.create_task(propagate_notify_events())
        try:
            await window_closed.wait()
        finally:
            await phile.asyncio.cancel_and_wait(propagating_task)

    except:

        def delete_window() -> None:
            """Ensure close events are emitted before deleting."""
            window.close()
            window.deleteLater()

        phile.PySide2.QtCore.call_soon_threadsafe(delete_window)
        raise


async def async_run(
    launcher_registry: phile.launcher.Registry,
) -> int:  # pragma: no cover
    event_view = launcher_registry.event_queue.__aiter__()
    await launcher_registry.start(gui_name := 'phile.notify.watchdog')
    await launcher_registry.start(gui_name := 'phile.notify.pyside2')
    if not launcher_registry.is_running(gui_name):
        return 1
    expected_event = phile.launcher.Event(
        type=phile.launcher.EventType.STOP, entry_name=gui_name
    )
    async for event in event_view:
        if event == expected_event:
            break
    return 0


def main() -> int:  # pragma: no cover
    try:
        return phile.main.run(async_run)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
