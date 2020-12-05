#!/usr/bin/env python3
"""
------------------------------------------------
Test :mod:`phile.tray.publishers.notify_monitor`
------------------------------------------------
"""

# Standard library.
import asyncio
import contextlib
import datetime
import pathlib
import tempfile
import threading
import unittest
import unittest.mock

# External dependencies.
import portalocker  # type: ignore[import]
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.notify
import phile.tray.publishers.notify_monitor
import phile.trigger
import phile.watchdog_extras
import test_phile.threaded_mock

wait_time = datetime.timedelta(seconds=2)


class TestMonitorStart(unittest.TestCase):
    """Tests :func:`~phile.tray.notify.start`."""

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )

    def set_up_observer(self) -> None:
        self.observer = phile.watchdog_extras.Observer()
        self.addCleanup(self.observer.stop)
        self.observer.start()

    def set_up_tray_event_dispatcher(self) -> None:
        self.tray_dispatcher = dispatcher = (
            watchdog.events.FileSystemEventHandler()
        )
        dispatch_patcher = unittest.mock.patch.object(
            dispatcher,
            'dispatch',
            new_callable=test_phile.threaded_mock.ThreadedMock
        )
        self.tray_dispatch = dispatch_patcher.start()
        self.addCleanup(dispatch_patcher.stop)
        tray_directory = self.configuration.tray_directory
        tray_directory.mkdir(exist_ok=True)
        watch = self.observer.add_handler(
            event_handler=dispatcher, path=tray_directory
        )
        self.addCleanup(
            self.observer.remove_handler,
            event_handler=dispatcher,
            watch=watch
        )

    def set_up_worker_thread(self) -> None:
        self.monitor_stopped = threading.Event()
        self.monitor_started = threading.Event()
        self.worker_thread = threading.Thread(
            target=asyncio.run, args=(self.run_monitor_start(), )
        )
        self.addCleanup(self.tear_down_worker_thread)
        self.worker_thread.start()
        self.assertTrue(
            self.monitor_started.wait(timeout=wait_time.total_seconds())
        )

    async def run_monitor_start(self) -> None:
        running_loop = self.running_loop = asyncio.get_running_loop()
        main_task = self.main_task = running_loop.create_task(
            self.monitor.start()
        )
        # Callbacks are called in schedule order.
        # So `start` will be polled once before `started` event is set.
        running_loop.call_soon(self.monitor_started.set)
        with contextlib.suppress(asyncio.CancelledError):
            await main_task
        self.monitor_stopped.set()

    def tear_down_worker_thread(self) -> None:
        if not self.worker_thread.is_alive():
            return
        self.running_loop.call_soon_threadsafe(self.main_task.cancel)
        self.monitor_stopped.wait(timeout=wait_time.total_seconds())

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        self.monitor = phile.tray.publishers.notify_monitor.Monitor(
            configuration=self.configuration,
            watching_observer=self.observer
        )
        self.trigger_directory = (
            self.monitor.entry_point.trigger_directory
        )
        self.extra_entry_point = phile.trigger.EntryPoint(
            configuration=self.configuration,
            trigger_directory=self.trigger_directory
        )

    def test_start_initialises_directories_and_triggers(self) -> None:
        self.set_up_worker_thread()
        self.assertTrue(
            self.configuration.notification_directory.is_dir()
        )
        self.assertTrue(self.trigger_directory.is_dir())
        self.assertTrue(
            self.extra_entry_point.get_trigger_path('close').is_file()
        )
        self.assertTrue(not self.monitor.notify_tray_file.path.exists())

    def test_init_with_existing_notify_file(self) -> None:
        self.notify_file_to_find = notify_file = (
            phile.notify.File.from_path_stem(
                'init', configuration=self.configuration, text='first'
            )
        )
        notify_file.save()
        self.set_up_worker_thread()
        self.assertTrue(
            self.monitor_started.wait(timeout=wait_time.total_seconds())
        )
        self.assertTrue(self.monitor.notify_tray_file.path.is_file())

    def test_detects_new_notify_file(self) -> None:
        self.set_up_worker_thread()
        self.set_up_tray_event_dispatcher()
        new_file = phile.notify.File.from_path_stem(
            'new', configuration=self.configuration, text='new content'
        )
        new_file.save()
        self.tray_dispatch.assert_called_with_soon(
            watchdog.events.FileModifiedEvent(
                src_path=str(self.monitor.notify_tray_file.path)
            )
        )

    def test_detects_file_removal(self) -> None:
        self.test_init_with_existing_notify_file()
        self.set_up_tray_event_dispatcher()
        self.notify_file_to_find.path.unlink(missing_ok=True)
        self.tray_dispatch.assert_called_with_soon(
            watchdog.events.FileDeletedEvent(
                src_path=str(self.monitor.notify_tray_file.path)
            )
        )

    def test_close_trigger_closes(self) -> None:
        self.set_up_worker_thread()
        self.extra_entry_point.get_trigger_path('close').unlink()
        self.assertTrue(
            self.monitor_stopped.wait(timeout=wait_time.total_seconds())
        )


if __name__ == '__main__':
    unittest.main()
