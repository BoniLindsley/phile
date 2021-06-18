#!/usr/bin/env python3
"""
----------------------------------
Test :mod:`phile.trigger.watchdog`
----------------------------------
"""

# Standard library.
import asyncio
import contextlib
import pathlib
import typing
import unittest

# External dependencies.
import portalocker
import watchdog.events

# Internal packages.
import phile
import phile.asyncio
import phile.asyncio.pubsub
import phile.trigger
import phile.trigger.watchdog
import phile.watchdog.observers
import test_phile.threaded_mock
from test_phile.test_init import UsesCapabilities, UsesConfiguration
from test_phile.test_configuration.test_init import (
    UsesConfiguration as UsesConfigurationEntries
)
from test_phile.test_trigger.test_init import UsesRegistry
from test_phile.test_watchdog.test_init import UsesObserver


class TestProducer(
    UsesRegistry, UsesObserver, UsesConfiguration, UsesCapabilities,
    unittest.TestCase
):
    """Tests :func:`~phile.trigger.watchdog.Producer`."""

    def setUp(self) -> None:
        """Also tests constructor of View."""
        super().setUp()
        self.producer = phile.trigger.watchdog.Producer(
            capabilities=self.capabilities
        )
        self.set_up_callback_in_registry()
        self.set_up_trigger_file_monitoring()
        self.trigger_name = 'nothing'
        self.trigger_file_path = self.configuration.trigger_root / (
            self.trigger_name + self.configuration.trigger_suffix
        )

    def set_up_callback_in_registry(self) -> None:
        self.event_callback = test_phile.threaded_mock.ThreadedMock()
        self.trigger_registry.event_callback_map.append(
            self.event_callback
        )
        self.addCleanup(
            self.trigger_registry.event_callback_map.remove,
            self.event_callback,
        )

    def set_up_trigger_file_monitoring(self) -> None:
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

    def test_creating_file_binds_and_shows_trigger(self) -> None:
        with self.producer:
            self.assertTrue(not self.trigger_file_path.is_file())
            self.trigger_file_path.touch()
            self.event_callback.assert_called_with_soon(
                phile.trigger.Registry.bind,
                self.trigger_registry,
                self.trigger_name,
            )
            self.event_callback.assert_called_with_soon(
                phile.trigger.Registry.show,
                self.trigger_registry,
                self.trigger_name,
            )

    def test_deleting_file_unbinds_trigger(self) -> None:
        self.trigger_file_path.touch()
        with self.producer:
            self.trigger_registry.is_bound(self.trigger_name)
            self.trigger_file_path.unlink()
            self.event_callback.assert_called_with_soon(
                phile.trigger.Registry.unbind,
                self.trigger_registry,
                self.trigger_name,
            )

    def test_double_delete_should_be_ignored(self) -> None:
        # This can happen if a file is created and deleted
        # before the trigger list is updated.
        # In this case, the producer is sent two file update requests.
        # Both detects as deletion, and unbind occurs twice.
        # There are no reliable way to force this to happen,
        # so implementation detail is used to mimic it.
        with self.producer:
            # Not bound. Unbind to mimic a double unbind.
            self.producer._on_path_change(self.trigger_file_path)
            self.producer._on_path_change(self.trigger_file_path)

    def test_double_create_should_be_ignored(self) -> None:
        # This can happen if a file is created,
        # and then deleted and created again
        # before the trigger list is updated.
        # There are no reliable way to force this to happen,
        # so implementation detail is used to mimic it.
        with self.producer:
            self.trigger_file_path.touch()
            self.event_callback.assert_called_with_soon(
                phile.trigger.Registry.bind,
                self.trigger_registry,
                self.trigger_name,
            )
            # Already bound. Force it to try to double bind again.
            self.producer._on_path_change(self.trigger_file_path)
            self.producer._on_path_change(self.trigger_file_path)

    def test_activate_trigger_deletes_file(self) -> None:
        self.trigger_file_path.touch()
        with self.producer:
            self.trigger_registry.is_shown(self.trigger_name)
            self.trigger_registry.activate(self.trigger_name)
            self.dispatch_mock.dispatch.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(
                    str(self.trigger_file_path)
                )
            )

    def test_context_binds_and_unbinds_existing_file(self) -> None:
        trigger_one = 'one'
        trigger_two = 'two'
        trigger_path_one = self.configuration.trigger_root / (
            trigger_one + self.configuration.trigger_suffix
        )
        trigger_path_two = self.configuration.trigger_root / (
            trigger_two + self.configuration.trigger_suffix
        )
        self.assertTrue(not trigger_path_one.is_file())
        self.assertTrue(not trigger_path_two.is_file())
        trigger_path_one.touch()
        trigger_path_two.touch()
        self.dispatch_mock.dispatch.assert_called_with_soon(
            watchdog.events.FileCreatedEvent(str(trigger_path_one))
        )
        self.dispatch_mock.dispatch.assert_called_with_soon(
            watchdog.events.FileCreatedEvent(str(trigger_path_two))
        )
        self.assertTrue(trigger_path_one.is_file())
        self.assertTrue(trigger_path_two.is_file())
        self.assertTrue(not self.trigger_registry.is_bound(trigger_one))
        self.assertTrue(not self.trigger_registry.is_bound(trigger_two))
        with self.producer:
            self.assertTrue(self.trigger_registry.is_bound(trigger_one))
            self.assertTrue(self.trigger_registry.is_bound(trigger_two))
        self.assertTrue(not self.trigger_registry.is_bound(trigger_one))
        self.assertTrue(not self.trigger_registry.is_bound(trigger_two))


class TestView(
    UsesConfigurationEntries,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.trigger.watchdog.View`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.observer: phile.watchdog.asyncio.BaseObserver
        self.observer_view: (
            phile.asyncio.pubsub.View[watchdog.events.FileSystemEvent]
        )
        self.trigger_callback: test_phile.threaded_mock.ThreadedMock
        self.trigger_directory: pathlib.Path
        self.trigger_file_path: pathlib.Path
        self.trigger_name: str
        self.trigger_registry: phile.trigger.Registry
        self.view: phile.trigger.watchdog.View
        self.view_task: asyncio.Task[typing.Any]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trigger_directory = (
            self.configuration.state_directory_path /
            self.configuration.trigger_directory
        )
        self.trigger_directory.mkdir()
        self.observer = phile.watchdog.asyncio.Observer()
        event_queue = await self.observer.schedule(
            str(self.trigger_directory)
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.observer.unschedule(str(self.trigger_directory)),
        )
        self.observer_view = event_queue.__aiter__()
        self.trigger_callback = test_phile.threaded_mock.ThreadedMock()
        self.trigger_name = 'nothing'
        self.trigger_file_path = (
            self.trigger_directory /
            (self.trigger_name + self.configuration.trigger_suffix)
        )
        self.trigger_registry = phile.trigger.Registry()
        self.trigger_registry.bind(
            self.trigger_name, self.trigger_callback
        )
        self.addCleanup(self.trigger_registry.unbind, self.trigger_name)
        self.view = phile.trigger.watchdog.View(
            configuration=self.configuration,
            observer=self.observer,
            trigger_registry=self.trigger_registry,
        )
        self.view_task = await self.create_ready_view_task(
            view=self.view
        )

    async def create_ready_view_task(
        self,
        view: phile.trigger.watchdog.View,
    ) -> asyncio.Task[typing.Any]:
        ready = asyncio.get_running_loop().create_future()
        view_task = asyncio.create_task(view.run(ready=ready))

        async def clean_up() -> None:
            if view_task.cancel():
                with contextlib.suppress(asyncio.CancelledError):
                    await view_task

        self.addCleanup(clean_up)
        await ready
        return view_task

    async def wait_for_event(
        self, expected_event: watchdog.events.FileSystemEvent
    ) -> None:

        async def get_event_until() -> None:
            async for event in self.observer_view:
                if event == expected_event:
                    break

        await phile.asyncio.wait_for(get_event_until())

    async def test_run_raises_if_trigger_directory_in_use(self) -> None:
        with self.assertRaises(portalocker.LockException):
            another_view = phile.trigger.watchdog.View(
                configuration=self.configuration,
                observer=self.observer,
                trigger_registry=self.trigger_registry,
            )
            ready = asyncio.get_running_loop().create_future()
            await phile.asyncio.wait_for(another_view.run(ready=ready))

    async def test_creates_visible_file_triggers(self) -> None:
        # Undo some of the initialisation first.
        self.view_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.view_task
        # Show a trigger before redo-ing the initialisation.
        self.trigger_registry.show(self.trigger_name)
        self.view_task = await self.create_ready_view_task(
            view=self.view
        )
        # It should be picked up by the initialisation.
        await self.wait_for_event(
            watchdog.events.FileCreatedEvent(
                str(self.trigger_file_path)
            )
        )

    async def test_showing_trigger_creates_file(self) -> None:
        self.assertTrue(not self.trigger_file_path.is_file())
        self.trigger_registry.show(self.trigger_name)
        await self.wait_for_event(
            watchdog.events.FileCreatedEvent(
                str(self.trigger_file_path)
            )
        )

    async def test_activating_trigger_deletes_file(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        self.trigger_registry.activate(self.trigger_name)
        await self.wait_for_event(
            watchdog.events.FileDeletedEvent(
                str(self.trigger_file_path)
            )
        )

    async def test_hiding_trigger_deletes_file(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        self.trigger_registry.hide(self.trigger_name)
        await self.wait_for_event(
            watchdog.events.FileDeletedEvent(
                str(self.trigger_file_path)
            )
        )

    async def test_unbinding_trigger_is_ignored(self) -> None:
        new_trigger_name = 'something'
        self.trigger_registry.bind(new_trigger_name, lambda: None)
        self.trigger_registry.unbind(new_trigger_name)
        # Force an action that would produce an event.
        # If the expected event is received,
        # there can be some certainty that un/binding was ignored.
        await self.test_showing_trigger_creates_file()

    async def test_deleting_file_activates_trigger(self) -> None:
        self.trigger_registry.show(self.trigger_name)
        await self.wait_for_event(
            watchdog.events.FileCreatedEvent(
                str(self.trigger_file_path)
            )
        )
        self.trigger_file_path.unlink()
        await self.wait_for_event(
            watchdog.events.FileDeletedEvent(
                str(self.trigger_file_path)
            )
        )
        self.trigger_callback.assert_called_with_soon()

    async def test_deleting_non_trigger_file_does_nothing(self) -> None:
        wrong_file = pathlib.Path(str(self.trigger_file_path) + 'wrong')
        wrong_file.touch()
        wrong_file.unlink()
        await self.wait_for_event(
            watchdog.events.FileDeletedEvent(str(wrong_file))
        )
        # Force an action that would produce an event.
        # If the expected event is received,
        # there can be some certainty that un/binding was ignored.
        await self.test_showing_trigger_creates_file()

    async def test_deleting_file_of_unbound_trigger_is_ignored(
        self
    ) -> None:
        unbound_trigger_file_path = self.trigger_directory / (
            'unbound' + self.configuration.trigger_suffix
        )
        unbound_trigger_file_path.touch()
        unbound_trigger_file_path.unlink()
        await self.wait_for_event(
            watchdog.events.FileDeletedEvent(
                str(unbound_trigger_file_path)
            )
        )
        # Force an action that would produce an event.
        # If the expected event is received,
        # there can be some certainty that un/binding was ignored.
        await self.test_showing_trigger_creates_file()


if __name__ == '__main__':
    unittest.main()
