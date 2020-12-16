#!/usr/bin/env python3
"""
--------------------------------------------------
Test :mod:`phile.tray.publishers.datetime_display`
--------------------------------------------------
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
import phile.tray.publishers.datetime_display
import phile.trigger
import phile.watchdog_extras
import test_phile.threaded_mock

wait_time = datetime.timedelta(seconds=2)


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.tray_files = (
            phile.tray.publishers.datetime_display._TrayFiles(
                configuration=self.configuration
            )
        )
        self.now = datetime.datetime(2222, 11, 1, 00, 59)
        tray_directory = self.configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '90-phile-datetime-display-1-year.tray',
            tray_directory / '90-phile-datetime-display-2-month.tray',
            tray_directory / '90-phile-datetime-display-3-day.tray',
            tray_directory / '90-phile-datetime-display-4-weekday.tray',
            tray_directory / '90-phile-datetime-display-5-hour.tray',
            tray_directory / '90-phile-datetime-display-6-minute.tray',
        )
        self.expected_text_icons = (
            ' 2222', '-11', '-01', ' 5', ' 00', ':59'
        )

    def assert_files_updated(self) -> None:
        for path, value in zip(
            self.expected_tray_files, self.expected_text_icons
        ):
            self.assertTrue(path.exists())
            with path.open() as file:
                self.assertEqual(file.readline(), value)

    def assert_files_missing(self) -> None:
        for path in self.expected_tray_files:
            self.assertTrue(not path.exists())

    def test_update(self) -> None:
        self.tray_files.update(self.now)
        self.assert_files_updated()

    def test_unlink(self) -> None:
        self.tray_files.update(self.now)
        self.tray_files.unlink()
        self.assert_files_missing()

    def test_context_manager(self) -> None:
        with self.tray_files as files:
            files.update(self.now)
            self.assert_files_updated()
        self.assert_files_missing()


class TestRun(unittest.TestCase):

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
        self.dispatcher = dispatcher = (
            test_phile.threaded_mock.ThreadedMock()
        )
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
        self.expected_tray_files = (
            tray_directory / '90-phile-datetime-display-1-year.tray',
            tray_directory / '90-phile-datetime-display-2-month.tray',
            tray_directory / '90-phile-datetime-display-3-day.tray',
            tray_directory / '90-phile-datetime-display-4-weekday.tray',
            tray_directory / '90-phile-datetime-display-5-hour.tray',
            tray_directory / '90-phile-datetime-display-6-minute.tray',
        )

    def assert_files_created(self) -> None:
        for file in self.expected_tray_files:
            self.dispatcher.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(str(file))
            )

    def assert_files_deleted(self) -> None:
        for file in self.expected_tray_files:
            self.dispatcher.dispatch.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(str(file))
            )

    def set_up_worker_thread(self) -> None:
        self.run_stopped = threading.Event()
        self.run_started = threading.Event()
        self.worker_thread = threading.Thread(
            target=asyncio.run, args=(self.run_start(), ), daemon=True
        )
        self.addCleanup(self.tear_down_worker_thread)
        self.worker_thread.start()
        self.assertTrue(
            self.run_started.wait(timeout=wait_time.total_seconds())
        )

    async def run_start(self) -> None:
        running_loop = self.running_loop = asyncio.get_running_loop()
        main_task = self.main_task = running_loop.create_task(
            phile.tray.publishers.datetime_display.run(
                configuration=self.configuration,
                watching_observer=self.observer
            )
        )
        # Callbacks are called in schedule order.
        # So `run` will be polled once before `started` event is set.
        running_loop.call_soon(self.run_started.set)
        with contextlib.suppress(asyncio.CancelledError):
            await main_task
        self.run_stopped.set()

    def tear_down_worker_thread(self) -> None:
        with contextlib.suppress(RuntimeError):
            self.running_loop.call_soon_threadsafe(self.main_task.cancel)
        self.run_stopped.wait(timeout=wait_time.total_seconds())

    def set_up_new_entry_point(self) -> None:
        self.entry_point = entry_point = phile.trigger.EntryPoint(
            configuration=self.configuration,
            trigger_directory=pathlib.Path('phile-datetime-display')
        )
        self.trigger_directory = entry_point.trigger_directory

    def activate_trigger(self, trigger_name: str) -> None:
        self.entry_point.get_trigger_path(trigger_name).unlink()

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        self.set_up_tray_event_dispatcher()
        self.set_up_worker_thread()
        self.set_up_new_entry_point()

    def test_initialises_monitored_directories_and_files(self) -> None:
        entry_point = self.entry_point
        self.assertTrue(self.configuration.tray_directory.is_dir())
        self.assertTrue(self.trigger_directory.is_dir())
        self.assertTrue(entry_point.get_trigger_path('close').is_file())
        self.assertTrue(entry_point.get_trigger_path('hide').is_file())
        self.assertTrue(
            not entry_point.get_trigger_path('show').exists()
        )
        self.assertTrue(not self.run_stopped.is_set())

    def test_initialisation_creates_tray_files(self) -> None:
        """
        Ensure tray files are created.

        Since the files are already created or updated with values
        by delegating to `_TrayFiles`,
        assume that the file contents are created properly,
        and only check for the file existence.
        """
        self.assert_files_created()

    def test_close_removes_tray_files(self) -> None:
        self.activate_trigger('close')
        self.assert_files_deleted()

    def test_hide_removes_tray_files(self) -> None:
        self.activate_trigger('hide')
        self.assert_files_deleted()

    def test_show_recreates_tray_files(self) -> None:
        self.activate_trigger('hide')
        self.assert_files_deleted()
        self.dispatcher.dispatch.reset_mock()
        self.activate_trigger('show')
        self.assert_files_created()


if __name__ == '__main__':
    unittest.main()
