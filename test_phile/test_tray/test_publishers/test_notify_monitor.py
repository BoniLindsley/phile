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
import watchdog.events
import watchdog.observers

# Internal packages.
import phile
import phile.notify
import phile.tray.publishers.notify_monitor
import phile.watchdog.observers
import test_phile.threaded_mock

wait_time = datetime.timedelta(seconds=2)


class TestMonitorStart(unittest.TestCase):
    """Tests :func:`~phile.tray.publishers.notify_monitor.monitor`."""

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = configuration = phile.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        self.capabilities = capabilities = phile.Capabilities()
        capabilities.set(configuration)

    def set_up_observer(self) -> None:
        self.observer = observer = watchdog.observers.Observer()
        self.addCleanup(observer.stop)
        observer.start()
        BaseObserver = watchdog.observers.api.BaseObserver
        self.capabilities[BaseObserver] = observer

    def set_up_tray_event_dispatcher(self) -> None:
        dispatcher = watchdog.events.FileSystemEventHandler()
        dispatch_patcher = unittest.mock.patch.object(
            dispatcher,
            'dispatch',
            new_callable=test_phile.threaded_mock.ThreadedMock
        )
        self.tray_dispatch = dispatch_patcher.start()
        self.addCleanup(dispatch_patcher.stop)
        tray_directory = self.configuration.tray_directory
        tray_directory.mkdir(exist_ok=True)
        watch = phile.watchdog.observers.add_handler(
            observer=self.observer,
            event_handler=dispatcher,
            path=tray_directory,
        )
        self.addCleanup(
            phile.watchdog.observers.remove_handler,
            observer=self.observer,
            event_handler=dispatcher,
            watch=watch
        )

    def set_up_worker_thread(self) -> None:
        self.monitor_stopped = threading.Event()
        self.monitor_started = threading.Event()
        self.worker_thread = threading.Thread(
            target=asyncio.run,
            args=(self.run_monitor_start(), ),
            daemon=True
        )
        self.addCleanup(self.tear_down_worker_thread)
        self.worker_thread.start()
        self.assertTrue(
            self.monitor_started.wait(timeout=wait_time.total_seconds())
        )

    async def run_monitor_start(self) -> None:
        running_loop = self.running_loop = asyncio.get_running_loop()
        main_task = self.main_task = running_loop.create_task(
            self.monitor
        )
        # Callbacks are called in schedule order.
        # So `start` will be polled once before `started` event is set.
        running_loop.call_soon(self.monitor_started.set)
        with contextlib.suppress(asyncio.CancelledError):
            await main_task
        self.monitor_stopped.set()

    def tear_down_worker_thread(self) -> None:
        with contextlib.suppress(RuntimeError):
            self.running_loop.call_soon_threadsafe(self.main_task.cancel)
        self.monitor_stopped.wait(timeout=wait_time.total_seconds())

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        configuration = self.configuration
        self.notify_tray_file = phile.tray.File.from_path_stem(
            configuration=configuration,
            path_stem='30-phile-notify-tray',
            text_icon=' N'
        )
        self.monitor = phile.tray.publishers.notify_monitor.run(
            capabilities=self.capabilities
        )

    def test_can_be_cancelled(self) -> None:
        self.set_up_worker_thread()

    def test_start_initialises_directories(self) -> None:
        self.set_up_worker_thread()
        self.assertTrue(
            self.configuration.notification_directory.is_dir()
        )
        self.assertTrue(not self.notify_tray_file.path.exists())

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
        self.assertTrue(self.notify_tray_file.path.is_file())

    def test_detects_new_notify_file(self) -> None:
        self.set_up_worker_thread()
        self.set_up_tray_event_dispatcher()
        new_file = phile.notify.File.from_path_stem(
            'new', configuration=self.configuration, text='new content'
        )
        new_file.save()
        self.tray_dispatch.assert_called_with_soon(
            watchdog.events.FileModifiedEvent(
                src_path=str(self.notify_tray_file.path)
            )
        )

    def test_detects_file_removal(self) -> None:
        self.test_init_with_existing_notify_file()
        self.set_up_tray_event_dispatcher()
        self.notify_file_to_find.path.unlink(missing_ok=True)
        self.tray_dispatch.assert_called_with_soon(
            watchdog.events.FileDeletedEvent(
                src_path=str(self.notify_tray_file.path)
            )
        )


if __name__ == '__main__':
    unittest.main()
