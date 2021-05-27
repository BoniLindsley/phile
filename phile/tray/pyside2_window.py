#!/usr/bin/env python3
"""
-----------------------------
Tray GUI window using PySide2
-----------------------------
"""

# Standard libraries.
import asyncio
import contextlib
import typing

# External dependencies.
import PySide2.QtWidgets

# Internal modules.
import phile.PySide2.QtCore
import phile.pubsub_event
import phile.tray


class MainWindow(PySide2.QtWidgets.QMainWindow):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.tray_content = tray_content = PySide2.QtWidgets.QLabel()
        self.setCentralWidget(tray_content)


async def run(
    pyside2_executor: phile.PySide2.QtCore.Executor,
    full_text_publisher: phile.tray.FullTextPublisher,
) -> None:
    loop = asyncio.get_running_loop()
    # Get the next event as soon as possible to avoid missing any.
    text_subscriber = phile.pubsub_event.Subscriber(
        publisher=full_text_publisher,
    )
    main_window_closed = asyncio.Event()
    # GUI functions must be called in GUI main thread.
    run_in_executor = loop.run_in_executor
    main_window = await run_in_executor(pyside2_executor, MainWindow)
    try:

        def set_closed_event(
            qobject: typing.Optional[PySide2.QtCore.QObject] = None,
        ) -> None:
            del qobject
            loop.call_soon_threadsafe(main_window_closed.set)

        def on_start() -> None:
            main_window.destroyed.connect(set_closed_event)
            main_window.setAttribute(PySide2.QtCore.Qt.WA_DeleteOnClose)
            main_window.show()

        async def propagate_text_changes() -> None:
            while current_text := await text_subscriber.pull():
                await run_in_executor(
                    pyside2_executor,
                    main_window.tray_content.setText,
                    current_text,
                )

        await run_in_executor(pyside2_executor, on_start)
        propagating_task = asyncio.create_task(propagate_text_changes())
        try:
            await main_window_closed.wait()
        finally:
            if propagating_task.cancel():
                with contextlib.suppress(asyncio.CancelledError):
                    await propagating_task

    except:

        def delete_window() -> None:
            """Ensure close events are emitted before deleting."""
            main_window.close()
            main_window.deleteLater()

        await run_in_executor(pyside2_executor, delete_window)
        raise
