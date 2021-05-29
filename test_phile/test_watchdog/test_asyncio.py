#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.watchdog.asyncio`
-----------------------------------
"""

# Standard library.
import pathlib
import tempfile
import typing
import unittest
import unittest.mock

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub
import phile.watchdog.asyncio
import phile.watchdog.observers


class StartFailed(Exception):
    pass


class TestBaseObserver(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.watchdog.asyncio.BaseObserver`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.event_emitter_class_mock: unittest.mock.Mock
        self.observer: phile.watchdog.asyncio.BaseObserver
        self.watched_directory: tempfile.TemporaryDirectory[str]

    async def asyncSetUp(self) -> None:
        watched_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(watched_directory.cleanup)
        self.watched_directory = watched_directory
        emitter_patcher = unittest.mock.patch(
            'phile.watchdog.asyncio.EventEmitter',
            autospec=True,
        )
        self.event_emitter_class_mock = emitter_patcher.start()
        self.addCleanup(emitter_patcher.stop)
        self.observer = phile.watchdog.asyncio.BaseObserver(
            emitter_class=self.event_emitter_class_mock,
        )

    def test_has_expected_attributes(self) -> None:
        self.assertEqual(
            self.observer.timeout,
            watchdog.observers.api.DEFAULT_OBSERVER_TIMEOUT
        )

    async def test_schedule_starts_and_unschedule_stops_emitter(
        self
    ) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        emitter_mock.is_alive.return_value = False
        await phile.asyncio.wait_for(
            self.observer.schedule(self.watched_directory.name)
        )
        try:
            emitter_mock.start.assert_called_once()
            emitter_mock.is_alive.return_value = True
        finally:
            await phile.asyncio.wait_for(
                self.observer.unschedule(self.watched_directory.name),
            )
            emitter_mock.stop.assert_called_once()

    async def test_schedule_returns_queue_and_unschedule_stops_it(
        self
    ) -> None:
        event_queue = await phile.asyncio.wait_for(
            self.observer.schedule(self.watched_directory.name)
        )
        try:
            self.assertIsInstance(
                event_queue, phile.watchdog.asyncio.EventQueue
            )
        finally:
            view = event_queue.__aiter__()
            await phile.asyncio.wait_for(
                self.observer.unschedule(self.watched_directory.name),
            )
            with self.assertRaises(StopAsyncIteration):
                await phile.asyncio.wait_for(view.__anext__())

    async def test_open_context_manager_starts_and_stops_emitter(
        self
    ) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        async with self.observer.open(self.watched_directory.name):
            emitter_mock.start.assert_called_once()
        emitter_mock.stop.assert_called_once()

    async def test_open_returns_queue_and_stops_it_on_exit(self) -> None:
        async with self.observer.open(
            self.watched_directory.name
        ) as event_queue:
            self.assertIsInstance(
                event_queue, phile.watchdog.asyncio.EventQueue
            )
            view = event_queue.__aiter__()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(view.__anext__())

    async def test_schedule_not_stopping_if_start_fails(self) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        emitter_mock.is_alive.return_value = False
        emitter_mock.start.side_effect = StartFailed
        with self.assertRaises(StartFailed):
            await phile.asyncio.wait_for(
                self.observer.schedule(self.watched_directory.name)
            )
        emitter_mock.stop.assert_not_called()

    async def test_schedule_not_stopping_queue_if_start_fails(
        self
    ) -> None:
        # Cannot really ensure it is not called.
        # Test for coverage.
        queue_patcher = unittest.mock.patch(
            'phile.watchdog.asyncio.EventQueue',
            autospec=True,
        )
        event_queue_class_mock = queue_patcher.start()
        self.addCleanup(queue_patcher.stop)
        event_queue_class_mock.side_effect = StartFailed
        # The mocking has to be done before the observer is created
        # because the mocked class is used in the constructor.
        self.observer = phile.watchdog.asyncio.BaseObserver(
            emitter_class=self.event_emitter_class_mock,
        )
        emitter_mock = self.event_emitter_class_mock.return_value
        emitter_mock.is_alive.return_value = False
        with self.assertRaises(StartFailed):
            await phile.asyncio.wait_for(
                self.observer.schedule(self.watched_directory.name)
            )
        emitter_mock.stop.assert_not_called()
        event_queue_class_mock.return_value.put_done.assert_not_called()

    async def test_schedule_can_be_stacked(self) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        async with self.observer.open(
            self.watched_directory.name
        ) as event_queue:
            async with self.observer.open(
                self.watched_directory.name
            ) as another_queue:
                self.assertIs(another_queue, event_queue)
            emitter_mock.stop.assert_not_called()
        emitter_mock.stop.assert_called_once()


class TestObserver(unittest.IsolatedAsyncioTestCase):
    """Tests :class:`~phile.watchdog.asyncio.Observer`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.observer: phile.watchdog.asyncio.Observer
        self.watched_directory: tempfile.TemporaryDirectory[str]

    async def asyncSetUp(self) -> None:
        watched_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(watched_directory.cleanup)
        self.watched_directory = watched_directory
        self.observer = phile.watchdog.asyncio.Observer()

    async def test_is_base_observer(self) -> None:
        self.assertIsInstance(
            self.observer,
            phile.watchdog.asyncio.BaseObserver,
        )

    async def test_detects_create_event(self) -> None:
        async with self.observer.open(
            self.watched_directory.name
        ) as event_queue:
            view = event_queue.__aiter__()
            watched_path = pathlib.Path(self.watched_directory.name)
            file_path = watched_path / 'touched.txt'
            file_path.touch()
            event = await phile.asyncio.wait_for(view.__anext__())
            self.assertEqual(
                event,
                watchdog.events.FileCreatedEvent(str(file_path)),
            )
