#!/usr/bin/env python3
"""
-----------------------------------------
Test :mod:`phile.tray.publishers.battery`
-----------------------------------------
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
import psutil  # type: ignore[import]
import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.notify
import phile.tray.publishers.battery
import phile.trigger
import phile.watchdog_extras
import test_phile.threaded_mock

wait_time = datetime.timedelta(seconds=2)


class TestFile(unittest.TestCase):

    def test_abstract_update(self) -> None:
        file = phile.tray.publishers.battery.File(pathlib.Path())
        with self.assertRaises(NotImplementedError):
            file.update(None)


class TestPercentageFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )

    def test_update(self) -> None:
        status = psutil._common.sbattery(
            percent=42, secsleft=0, power_plugged=False
        )
        self.file.update(status)
        self.assertEqual(self.file.text_icon, ' B:42%')

    def test_update_none(self) -> None:
        file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )
        status = None
        self.file.update(status)
        self.assertEqual(self.file.text_icon, ' B:-?%')


class TestTimeFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.battery.TimeFile(
            pathlib.Path()
        )

    def test_update(self) -> None:
        status = psutil._common.sbattery(
            percent=0, secsleft=32767, power_plugged=False
        )
        self.file.update(status)
        self.assertEqual(self.file.text_icon, '=9h06')

    def test_update_none(self) -> None:
        file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )
        status = None
        self.file.update(status)
        self.assertEqual(self.file.text_icon, '')


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )

    def set_up_psutil_battery_sensor_mock(self) -> None:
        patch = unittest.mock.patch('psutil.sensors_battery')
        self.addCleanup(patch.stop)
        self.battery_sensor_mock = mock = patch.start()
        mock.return_value = psutil._common.sbattery(
            percent=42, secsleft=0, power_plugged=False
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_psutil_battery_sensor_mock()
        self.tray_files = (
            phile.tray.publishers.battery._TrayFiles(
                configuration=self.configuration
            )
        )
        tray_directory = self.configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '70-phile-tray-battery-1-percentage.tray',
            tray_directory / '70-phile-tray-battery-2-time.tray',
        )

    def test_update(self) -> None:
        self.tray_files.update()
        for path in self.expected_tray_files:
            self.assertTrue(path.exists())

    def test_unlink(self) -> None:
        self.tray_files.update()
        self.tray_files.unlink()
        for path in self.expected_tray_files:
            self.assertTrue(not path.exists())

    def test_context_manager(self) -> None:
        with self.tray_files as files:
            files.update()
            for path in self.expected_tray_files:
                self.assertTrue(path.exists())
        for path in self.expected_tray_files:
            self.assertTrue(not path.exists())


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

    def set_up_psutil_battery_sensor_mock(self) -> None:
        patch = unittest.mock.patch('psutil.sensors_battery')
        self.addCleanup(patch.stop)
        self.battery_sensor_mock = mock = patch.start()
        mock.return_value = psutil._common.sbattery(
            percent=42, secsleft=0, power_plugged=False
        )

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
            tray_directory / '70-phile-tray-battery-1-percentage.tray',
            tray_directory / '70-phile-tray-battery-2-time.tray',
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
            phile.tray.publishers.battery.run(
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
            trigger_directory=pathlib.Path('phile-tray-battery')
        )
        self.trigger_directory = entry_point.trigger_directory

    def activate_trigger(self, trigger_name: str) -> None:
        self.entry_point.get_trigger_path(trigger_name).unlink()

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        self.set_up_psutil_battery_sensor_mock()
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
