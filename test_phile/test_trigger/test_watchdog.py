#!/usr/bin/env python3
"""
----------------------------------
Test :mod:`phile.trigger.watchdog`
----------------------------------
"""

# Standard library.
import asyncio
import pathlib
import typing
import unittest

# External dependencies.
# TODO[portalocker issue #60]: Remove type: ignore.
# Type hinting is not yet activated.
import portalocker  # type: ignore[import]
import watchdog.events

# Internal packages.
import phile
import phile.asyncio
import phile.trigger
import phile.trigger.watchdog
import phile.watchdog.observers
import test_phile.threaded_mock
from test_phile.test_init import UsesCapabilities, UsesConfiguration
from test_phile.test_trigger.test_init import UsesRegistry
from test_phile.test_watchdog.test_init import UsesObserver


class TestView(
    UsesRegistry, UsesObserver, UsesConfiguration, UsesCapabilities,
    unittest.TestCase
):
    """Tests :func:`~phile.trigger.watchdog.View`."""

    def setUp(self) -> None:
        """Also tests constructor of View."""
        super().setUp()
        self.view = phile.trigger.watchdog.View(
            capabilities=self.capabilities
        )
        self.set_up_trigger_in_registry()
        self.set_up_trigger_file_monitoring()

    def set_up_trigger_in_registry(self) -> None:
        self.trigger_name = 'nothing'
        self.trigger_callback = test_phile.threaded_mock.ThreadedMock()
        self.trigger_registry.bind(
            self.trigger_name, self.trigger_callback
        )
        self.addCleanup(self.trigger_registry.unbind, self.trigger_name)

    def set_up_trigger_file_monitoring(self) -> None:
        self.trigger_file_path = self.configuration.trigger_root / (
            self.trigger_name + self.configuration.trigger_suffix
        )
        self.dispatch_mock = test_phile.threaded_mock.ThreadedMock()
        self.configuration.trigger_root.mkdir(
            parents=True, exist_ok=True
        )
        watchdog_watch = phile.watchdog.observers.add_handler(
            observer=self.watchdog_observer,
            event_handler=self.dispatch_mock,
            path=self.configuration.trigger_root,
        )
        self.addCleanup(
            phile.watchdog.observers.remove_handler,
            observer=self.watchdog_observer,
            event_handler=self.dispatch_mock,
            watch=watchdog_watch,
        )

    def test_available_exceptions(self) -> None:
        with self.assertRaises(portalocker.LockException):
            raise phile.trigger.watchdog.View.DirectoryInUse()

    def test_enter_raises_if_trigger_root_already_in_use(self) -> None:
        with self.view:
            with self.assertRaises(
                phile.trigger.watchdog.View.DirectoryInUse
            ):
                phile.trigger.watchdog.View(
                    capabilities=self.capabilities
                ).__enter__()

    def test_showing_trigger_creates_file(self) -> None:
        with self.view:
            self.assertTrue(not self.trigger_file_path.is_file())
            self.trigger_registry.show(self.trigger_name)
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )

    def test_unbinding_trigger_is_ignored(self) -> None:
        # Cannot test that it is really ignored.
        # But ensure that the event at least processed without problems.
        with self.view:
            self.assertTrue(not self.trigger_file_path.is_file())
            self.trigger_registry.unbind(self.trigger_name)

    def test_activating_trigger_deletes_file(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        with self.view:
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )
            self.assertTrue(self.trigger_file_path.is_file())
            self.dispatch_mock.reset_mock()
            self.trigger_registry.activate(self.trigger_name)
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(
                    str(self.trigger_file_path)
                )
            )

    def test_hiding_trigger_deletes_file(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        with self.view:
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )
            self.assertTrue(self.trigger_file_path.is_file())
            self.dispatch_mock.reset_mock()
            self.trigger_registry.hide(self.trigger_name)
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(
                    str(self.trigger_file_path)
                )
            )

    def test_enter_creates_visible_file_triggers(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        self.assertTrue(not self.trigger_file_path.is_file())
        with self.view:
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )
            self.assertTrue(self.trigger_file_path.is_file())

    def test_deleting_file_activates_trigger(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        with self.view:
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )
            self.assertTrue(self.trigger_file_path.is_file())
            self.trigger_file_path.unlink()
            self.trigger_callback.assert_called_with_soon()

    def test_deleting_non_trigger_file_does_nothing(self) -> None:
        # Cannot really test that there are no side effects.
        # We test for a specific one.
        # Trigger root and name with wrong extension.
        self.trigger_registry.show(self.trigger_name)
        with self.view:
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(
                    str(self.trigger_file_path)
                )
            )
            self.assertTrue(self.trigger_file_path.is_file())
            wrong_file = pathlib.Path(
                str(self.trigger_file_path) + 'wrong'
            )
            wrong_file.touch()
            wrong_file.unlink()


class TestRun(
    UsesRegistry, UsesObserver, UsesConfiguration, UsesCapabilities,
    unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.trigger.watchdog.Prompt`."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.set_up_trigger_file_monitoring()

    async def set_up_trigger_file_monitoring(self) -> None:
        loop = asyncio.get_running_loop()
        self.dispatch_event = asyncio.Event()

        def dispatch_callback(_event: typing.Any) -> typing.Any:
            loop.call_soon_threadsafe(self.dispatch_event.set)
            return unittest.mock.DEFAULT

        self.dispatch_mock = unittest.mock.Mock()
        self.dispatch_mock.dispatch.side_effect = dispatch_callback

        self.configuration.trigger_root.mkdir(
            parents=True, exist_ok=True
        )
        watchdog_watch = phile.watchdog.observers.add_handler(
            observer=self.watchdog_observer,
            event_handler=self.dispatch_mock,
            path=self.configuration.trigger_root,
        )
        self.addCleanup(
            phile.watchdog.observers.remove_handler,
            observer=self.watchdog_observer,
            event_handler=self.dispatch_mock,
            watch=watchdog_watch,
        )

    async def check_trigger_file_created(self, name: str) -> None:
        trigger_path = self.configuration.trigger_root / (
            name + self.configuration.trigger_suffix
        )
        expected_event = watchdog.events.FileCreatedEvent(
            str(trigger_path)
        )
        try:
            while unittest.mock.call(
                expected_event
            ) not in self.dispatch_mock.dispatch.call_args_list:
                await self.dispatch_event.wait()
                self.dispatch_event.clear()
        except:
            self.dispatch_mock.dispatch.assert_called_with(
                expected_event
            )

    async def test_creates_stop_trigger_and_stops_when_activated(
        self
    ) -> None:
        trigger_name = 'phile.trigger.watchdog.stop'
        task = asyncio.create_task(
            phile.trigger.watchdog.run(capabilities=self.capabilities)
        )
        self.addCleanup(task.cancel)
        await phile.asyncio.wait_for(
            self.check_trigger_file_created(trigger_name)
        )
        trigger_path = self.configuration.trigger_root / (
            trigger_name + self.configuration.trigger_suffix
        )
        trigger_path.unlink()
        await phile.asyncio.wait_for(task)


if __name__ == '__main__':
    unittest.main()
