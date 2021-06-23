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
import unittest.mock

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
from test_phile.test_configuration.test_init import UsesConfiguration
from test_phile.test_watchdog.test_asyncio import UsesObserver


class TestProducer(
    UsesObserver, UsesConfiguration, unittest.IsolatedAsyncioTestCase
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.callback_called: asyncio.Event
        self.event_callback: unittest.mock.MagicMock
        self.producer: phile.trigger.watchdog.Producer
        self.runner: asyncio.Task[typing.Any]
        self.trigger_directory: pathlib.Path
        self.trigger_file_path: pathlib.Path
        self.trigger_name: str
        self.trigger_registry: phile.trigger.Registry
        self.watchdog_view: (
            phile.asyncio.pubsub.View[watchdog.events.FileSystemEvent]
        )

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        loop = asyncio.get_running_loop()
        self.callback_called = callback_called = asyncio.Event()

        def callback_side_effect(
            *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            del args
            del kwargs
            loop.call_soon_threadsafe(callback_called.set)
            return unittest.mock.DEFAULT

        self.event_callback = unittest.mock.MagicMock(
            side_effect=callback_side_effect
        )
        self.trigger_directory = (
            self.configuration.state_directory_path /
            self.configuration.trigger_directory
        )
        self.trigger_directory.mkdir()
        self.trigger_name = 'nothing'
        self.trigger_file_path = self.trigger_directory / (
            self.trigger_name + self.configuration.trigger_suffix
        )
        self.trigger_registry = phile.trigger.Registry()
        self.trigger_registry.event_callback_map.append(
            self.event_callback
        )
        self.addCleanup(
            self.trigger_registry.event_callback_map.remove,
            self.event_callback,
        )
        self.watchdog_view = await self.schedule_watchdog_observer(
            path=self.trigger_directory
        )
        self.producer = phile.trigger.watchdog.Producer(
            configuration=self.configuration,
            observer=self.observer,
            trigger_registry=self.trigger_registry,
        )

    def set_up_runner(self) -> None:
        self.runner = asyncio.create_task(self.producer.run())
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            phile.asyncio.cancel_and_wait(self.runner)
        )

    async def assert_called_with_soon(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        expected_call = unittest.mock.call(*args, **kwargs)

        async def wait_for_call() -> None:
            while True:
                if expected_call in self.event_callback.call_args_list:
                    return
                await self.callback_called.wait()
                self.callback_called.clear()

        try:
            await phile.asyncio.wait_for(wait_for_call())
        except BaseException as original_error:
            try:
                self.assertIn(
                    expected_call, self.event_callback.call_args_list
                )
            except AssertionError as error:
                raise error from original_error
            raise

    async def test_creating_file_binds_and_shows_trigger(self) -> None:
        self.set_up_runner()
        self.assertTrue(not self.trigger_file_path.is_file())
        self.trigger_file_path.touch()
        await self.assert_called_with_soon(
            phile.trigger.Registry.bind,
            self.trigger_registry,
            self.trigger_name,
        )
        await self.assert_called_with_soon(
            phile.trigger.Registry.show,
            self.trigger_registry,
            self.trigger_name,
        )

    async def test_deleting_file_unbinds_trigger(self) -> None:
        self.trigger_file_path.touch()
        self.set_up_runner()
        await self.assert_called_with_soon(
            phile.trigger.Registry.bind,
            self.trigger_registry,
            self.trigger_name,
        )
        self.trigger_file_path.unlink()
        await self.assert_called_with_soon(
            phile.trigger.Registry.unbind,
            self.trigger_registry,
            self.trigger_name,
        )

    async def test_double_delete_should_be_ignored(self) -> None:
        # This can happen if a file is created and deleted
        # before the trigger list is updated.
        # In this case, the producer is sent two file update requests.
        # Both detects as deletion, and unbind occurs twice.
        # There are no reliable way to force this to happen,
        # so implementation detail is used to mimic it.
        #
        # Not bound. Unbind to mimic a double unbind.
        # pylint: disable=protected-access
        self.producer._on_path_change(self.trigger_file_path)
        self.producer._on_path_change(self.trigger_file_path)

    async def test_double_create_should_be_ignored(self) -> None:
        # This can happen if a file is created,
        # and then deleted and created again
        # before the trigger list is updated.
        # There are no reliable way to force this to happen,
        # so implementation detail is used to mimic it.
        self.set_up_runner()
        self.trigger_file_path.touch()
        await self.assert_called_with_soon(
            phile.trigger.Registry.bind,
            self.trigger_registry,
            self.trigger_name,
        )
        # Already bound. Force it to try to double bind again.
        # pylint: disable=protected-access
        self.producer._on_path_change(self.trigger_file_path)
        self.producer._on_path_change(self.trigger_file_path)

    async def test_activate_trigger_deletes_file(self) -> None:
        self.trigger_file_path.touch()
        self.set_up_runner()
        await self.assert_called_with_soon(
            phile.trigger.Registry.show,
            self.trigger_registry,
            self.trigger_name,
        )
        self.trigger_registry.activate(self.trigger_name)
        await self.assert_watchdog_emits(
            self.watchdog_view,
            watchdog.events.FileDeletedEvent(
                str(self.trigger_file_path)
            )
        )

    async def test_run__unbinds_on_exit(self) -> None:
        self.set_up_runner()
        self.trigger_file_path.touch()
        await self.assert_called_with_soon(
            phile.trigger.Registry.show,
            self.trigger_registry,
            self.trigger_name,
        )
        await phile.asyncio.cancel_and_wait(self.runner)
        await self.assert_called_with_soon(
            phile.trigger.Registry.show,
            self.trigger_registry,
            self.trigger_name,
        )


class TestView(
    UsesConfiguration,
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
