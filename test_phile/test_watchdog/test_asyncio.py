#!/usr/bin/env python3

# Standard library.
import asyncio
import collections.abc
import functools
import pathlib
import queue
import typing
import unittest
import unittest.mock

# External dependencies.
import watchdog.events
import watchdog.observers

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub
import phile.unittest
import phile.watchdog.asyncio
import phile.watchdog.observers

_T = typing.TypeVar('_T')


class StartFailed(Exception):
    pass


class TestEventView(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.called: asyncio.Event
        self.event_view: phile.watchdog.asyncio.EventView
        self.next_node: (
            phile.asyncio.pubsub.Node[watchdog.events.FileSystemEvent]
        )

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.called = called = asyncio.Event()
        self.next_node = (
            phile.asyncio.pubsub.Node[watchdog.events.FileSystemEvent]()
        )
        self.event_view = phile.watchdog.asyncio.EventView(
            next_node=self.next_node
        )

        async def aclose() -> None:
            called.set()

        self.event_view.aclose_callback = aclose

    async def test_aclose__calls_given_callable(self) -> None:
        self.assertFalse(self.called.is_set())
        await phile.asyncio.wait_for(self.event_view.aclose())
        self.assertTrue(self.called.is_set())

    async def test_aclose__is_idempotent(self) -> None:
        self.assertFalse(self.called.is_set())
        await phile.asyncio.wait_for(self.event_view.aclose())
        self.assertTrue(self.called.is_set())
        self.called.clear()
        await phile.asyncio.wait_for(self.event_view.aclose())
        self.assertFalse(self.called.is_set())

    async def test_aexit___calls_aclose(self) -> None:
        async with self.event_view:
            pass
        self.assertTrue(self.called.is_set())


class TestEventQueue(unittest.IsolatedAsyncioTestCase):

    async def test_put__puts_event(self) -> None:
        event_queue = phile.watchdog.asyncio.EventQueue()
        view = event_queue.__aiter__()
        expected_event = watchdog.events.FileCreatedEvent('')
        event_queue.put(
            event_data=(
                expected_event,
                watchdog.observers.api.ObservedWatch('', False)
            )
        )
        event = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(event, expected_event)


class EventEmitterMock:

    def __init__(  # pylint: disable=keyword-arg-before-vararg
        self,
        event_queue: watchdog.observers.api.EventQueue,
        watch: watchdog.observers.api.ObservedWatch,
        timeout: float = 1,
        *args: typing.Any,
        source_events: collections.abc.Iterable[
            watchdog.events.FileSystemEvent] = [],
        **kwargs: typing.Any
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._event_queue = event_queue
        self._loop = asyncio.get_running_loop()
        self._source_events = (
            queue.SimpleQueue[watchdog.events.FileSystemEvent]()
        )
        self._started = False
        self._stopped = False
        self._stopped_event = asyncio.Event()
        self.watch = watch
        self.timeout = timeout
        if source_events is not None:
            for event in source_events:
                self._source_events.put_nowait(event)

    @classmethod
    def create_emitter_class(
        cls,
        source_events: collections.abc.Iterable[
            watchdog.events.FileSystemEvent],
    ) -> collections.abc.Callable[[
        watchdog.observers.api.EventQueue,
        watchdog.observers.api.ObservedWatch,
        float,
    ], phile.watchdog.asyncio.EventEmitter]:
        return functools.partial(  # type: ignore[return-value]
            cls, source_events=source_events
        )

    def queue_event(
        self, event: watchdog.events.FileSystemEvent
    ) -> None:
        if self._stopped:
            raise RuntimeError
        if self._started:
            self._event_queue.put((event, self.watch))
        else:
            self._source_events.put_nowait(event)

    def start(self) -> None:
        self._started = True
        try:
            while True:
                self.queue_event(self._source_events.get_nowait())
        except queue.Empty:
            pass

    def stop(self) -> None:
        self._stopped = True
        self._loop.call_soon_threadsafe(self._stopped_event.set)

    def is_alive(self) -> bool:
        return self._started and not self._stopped

    async def async_join(self) -> None:
        await self._stopped_event.wait()


class TestEventEmitterMock(
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.emitter: EventEmitterMock
        self.event_queue: watchdog.observers.api.EventQueue
        self.expected_event: watchdog.events.FileSystemEvent
        self.watch: watchdog.observers.api.ObservedWatch

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.event_queue = watchdog.observers.api.EventQueue()
        self.watch = watchdog.observers.api.ObservedWatch(
            str(self.temporary_directory), False
        )
        self.emitter = EventEmitterMock(self.event_queue, self.watch)
        self.expected_event = watchdog.events.FileCreatedEvent(
            str(self.temporary_directory)
        )

    async def test_is_alive__is_false_by_default(self) -> None:
        self.assertFalse(self.emitter.is_alive())

    async def test_start__makes_is_alive(self) -> None:
        self.emitter.start()
        self.assertTrue(self.emitter.is_alive())

    async def test_stop__makes_not_is_alive(self) -> None:
        self.emitter.start()
        self.emitter.stop()
        self.assertFalse(self.emitter.is_alive())

    async def test_async_join__after_stop(self) -> None:
        self.emitter.start()
        self.emitter.stop()
        await phile.asyncio.wait_for(self.emitter.async_join())

    async def test_queue_event__puts_events_into_queue(self) -> None:
        self.emitter.start()
        self.emitter.queue_event(self.expected_event)
        received_event = self.event_queue.get_nowait()
        self.assertEqual(
            received_event, (self.expected_event, self.watch)
        )

    async def test_queue_event__does_not__queue_if_not_started(
        self
    ) -> None:
        self.emitter.queue_event(self.expected_event)
        self.assertTrue(self.event_queue.empty())

    async def test_queue_event__raises_if_stopped(self) -> None:
        self.emitter.start()
        self.emitter.stop()
        with self.assertRaises(RuntimeError):
            self.emitter.queue_event(self.expected_event)

    async def test_start__queue_events_if_any(self) -> None:
        self.emitter.queue_event(self.expected_event)
        self.emitter.start()
        received_event = self.event_queue.get_nowait()
        self.assertEqual(
            received_event, (self.expected_event, self.watch)
        )

    async def test_create_emitter_class__pre_queue_events(self) -> None:
        # It acts as a class.
        Emitter = (  # pylint: disable=invalid-name
            EventEmitterMock.create_emitter_class(
                source_events=(self.expected_event, )
            )
        )
        emitter = Emitter(self.event_queue, self.watch, 1)
        self.assertTrue(self.event_queue.empty())
        emitter.start()
        received_event = self.event_queue.get_nowait()
        self.assertEqual(
            received_event, (self.expected_event, self.watch)
        )


class TestBaseObserver(
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.event_emitter_class_mock: unittest.mock.Mock
        self.observer: phile.watchdog.asyncio.BaseObserver

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
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
            self.observer.schedule(self.temporary_directory)
        )
        try:
            emitter_mock.start.assert_called_once()
            emitter_mock.is_alive.return_value = True
        finally:
            await phile.asyncio.wait_for(
                self.observer.unschedule(self.temporary_directory)
            )
            emitter_mock.stop.assert_called_once()

    async def test_schedule_returns_queue_and_unschedule_stops_it(
        self
    ) -> None:
        event_view = await phile.asyncio.wait_for(
            self.observer.schedule(self.temporary_directory)
        )
        try:
            self.assertIsInstance(
                event_view, phile.watchdog.asyncio.EventView
            )
        finally:
            await phile.asyncio.wait_for(
                self.observer.unschedule(self.temporary_directory),
            )
            with self.assertRaises(StopAsyncIteration):
                await phile.asyncio.wait_for(event_view.__anext__())

    async def test_schedule__returns_cm_that_starts_and_stops_emitter(
        self
    ) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        async with await phile.asyncio.wait_for(
            self.observer.schedule(self.temporary_directory)
        ):
            emitter_mock.start.assert_called_once()
        emitter_mock.stop.assert_called_once()

    async def test_schedule__returns_view_ending_on_exit(self) -> None:
        async with await phile.asyncio.wait_for(
            self.observer.schedule(self.temporary_directory)
        ) as event_view:
            self.assertIsInstance(
                event_view, phile.watchdog.asyncio.EventView
            )
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_schedule_not_stopping_if_start_fails(self) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        emitter_mock.is_alive.return_value = False
        emitter_mock.start.side_effect = StartFailed
        with self.assertRaises(StartFailed):
            await phile.asyncio.wait_for(
                self.observer.schedule(self.temporary_directory)
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
                self.observer.schedule(self.temporary_directory)
            )
        emitter_mock.stop.assert_not_called()
        event_queue_class_mock.return_value.put_done.assert_not_called()

    async def test_schedule_can_be_stacked(self) -> None:
        emitter_mock = self.event_emitter_class_mock.return_value
        async with await phile.asyncio.wait_for(
            self.observer.schedule(self.temporary_directory)
        ) as event_view:
            async with await phile.asyncio.wait_for(
                self.observer.schedule(self.temporary_directory)
            ) as another_view:
                self.assertIs(
                    # pylint: disable=protected-access
                    another_view._next_node,
                    event_view._next_node,
                )
            emitter_mock.stop.assert_not_called()
        emitter_mock.stop.assert_called_once()


class TestObserver(
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.observer: phile.watchdog.asyncio.Observer

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.observer = phile.watchdog.asyncio.Observer()

    async def test_is_base_observer(self) -> None:
        self.assertIsInstance(
            self.observer,
            phile.watchdog.asyncio.BaseObserver,
        )

    async def test_detects_create_event(self) -> None:
        async with await phile.asyncio.wait_for(
            self.observer.schedule(self.temporary_directory)
        ) as event_view:
            file_path = self.temporary_directory / 'touched.txt'
            file_path.touch()
            event = await phile.asyncio.wait_for(event_view.__anext__())
            self.assertEqual(
                event,
                watchdog.events.FileCreatedEvent(str(file_path)),
            )


class UsesObserver(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.observer: phile.watchdog.asyncio.BaseObserver
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.observer = phile.watchdog.asyncio.Observer()

    async def assert_watchdog_emits(
        self,
        source_view: (
            phile.asyncio.pubsub.View[watchdog.events.FileSystemEvent]
        ),
        expected_event: watchdog.events.FileSystemEvent,
    ) -> None:
        received_events: list[watchdog.events.FileSystemEvent] = []

        async def run() -> None:
            async for event in source_view:
                if event == expected_event:
                    return
                received_events.append(event)

        try:
            await phile.asyncio.wait_for(run())
        except BaseException as error:
            message = (
                '{expected_event} not found.\n'
                'Received: {received_events}'.format(
                    expected_event=expected_event,
                    received_events=received_events,
                )
            )
            raise self.failureException(message) from error

    async def schedule_watchdog_observer(
        self, path: pathlib.Path
    ) -> phile.watchdog.asyncio.EventView:
        event_view = await phile.asyncio.wait_for(
            self.observer.schedule(path)
        )
        self.addAsyncCleanup(event_view.aclose)
        return event_view


class TestSplitFileMoveEvent(
    phile.unittest.UsesTemporaryDirectory, unittest.TestCase
):

    def test_ignores_directory_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        source_event = watchdog.events.DirCreatedEvent(str(event_path))
        self.assertEqual(
            phile.watchdog.asyncio.split_file_move_event(source_event),
            tuple(),
        )

    def test_returns_src_path_of_non_move_file_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        source_event = watchdog.events.FileCreatedEvent(str(event_path))
        self.assertEqual(
            phile.watchdog.asyncio.split_file_move_event(source_event),
            (source_event, ),
        )

    def test_returns_src_and_dest_paths_of_move_file_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        target_path = (self.temporary_directory / 'something.file_2')
        source_event = watchdog.events.FileMovedEvent(
            str(event_path), str(target_path)
        )
        self.assertEqual(
            phile.watchdog.asyncio.split_file_move_event(source_event),
            (
                watchdog.events.FileDeletedEvent(str(event_path)),
                watchdog.events.FileCreatedEvent(str(target_path)),
            ),
        )


class TestEventToFilePaths(
    phile.unittest.UsesTemporaryDirectory, unittest.TestCase
):

    def test_ignores_directory_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        source_event = watchdog.events.DirCreatedEvent(str(event_path))
        self.assertEqual(
            phile.watchdog.asyncio.event_to_file_paths(source_event),
            tuple(),
        )

    def test_returns_src_path_of_non_move_file_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        source_event = watchdog.events.FileCreatedEvent(str(event_path))
        self.assertEqual(
            phile.watchdog.asyncio.event_to_file_paths(source_event),
            (event_path, ),
        )

    def test_returns_src_and_dest_paths_of_move_file_event(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        target_path = (self.temporary_directory / 'something.file_2')
        source_event = watchdog.events.FileMovedEvent(
            str(event_path), str(target_path)
        )
        self.assertEqual(
            phile.watchdog.asyncio.event_to_file_paths(source_event),
            (event_path, target_path),
        )


class TestFilterPath(
    phile.unittest.UsesTemporaryDirectory, unittest.TestCase
):

    def test_returns_true_if_passes_filter(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        passes_filter = phile.watchdog.asyncio.filter_path(
            event_path,
            expected_parent=self.temporary_directory,
            expected_suffix='.file'
        )
        self.assertTrue(passes_filter)

    def test_returns_false_if_parent_directory_unexpected(self) -> None:
        event_path = (self.temporary_directory / 'something.file')
        passes_filter = phile.watchdog.asyncio.filter_path(
            event_path,
            expected_parent=self.temporary_directory / 's',
            expected_suffix='.file'
        )
        self.assertFalse(passes_filter)

    def test_returns_false_if_suffix_unexpected(self) -> None:
        event_path = (self.temporary_directory / 'something.file_wrong')
        passes_filter = phile.watchdog.asyncio.filter_path(
            event_path,
            expected_parent=self.temporary_directory,
            expected_suffix='.file'
        )
        self.assertFalse(passes_filter)


async def to_async_iter(
    source: collections.abc.Iterable[_T]
) -> collections.abc.AsyncIterable[_T]:
    for item in source:
        yield item


class TestMonitorFileExistence(
    UsesObserver,
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.expected_files: (
            list[tuple[pathlib.Path, typing.Optional[str]]]
        )
        self.loader: collections.abc.AsyncIterator[tuple[
            pathlib.Path, typing.Optional[str]]]
        self.watchdog_view: collections.abc.AsyncIterator[
            watchdog.events.FileSystemEvent]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.expected_files = []
        self.watchdog_view = await self.schedule_watchdog_observer(
            self.temporary_directory
        )
        self.loader = phile.watchdog.asyncio.load_changed_files(
            directory_path=self.temporary_directory,
            expected_suffix='.suf',
            watchdog_view=self.watchdog_view,
        )

    async def assert_returns(self, ) -> None:
        received_files: (
            list[tuple[pathlib.Path, typing.Optional[str]]]
        ) = []
        try:
            load_aiter = self.loader.__aiter__()
            for expected_file in self.expected_files:
                found = False
                while not found:
                    received_file = await load_aiter.__anext__()
                    received_files.append(received_file)
                    found = (received_file == expected_file)
        except BaseException as error:
            message = (
                'Did not receive\n{expected_files}\n'
                'Received\n{received_files}'.format(
                    expected_files=self.expected_files,
                    received_files=received_files,
                )
            )
            raise self.failureException(message) from error

    async def test_true_for_creation(self) -> None:
        src_path = self.temporary_directory / 'a.suf'
        source_events: list[watchdog.events.FileSystemEvent] = [
            watchdog.events.FileCreatedEvent(str(src_path))
        ]
        existences: list[tuple[pathlib.Path, bool]] = [
            (path, existence) async for path, existence in
            phile.watchdog.asyncio.monitor_file_existence(
                directory_path=self.temporary_directory,
                expected_suffix='.suf',
                watchdog_view=to_async_iter(source_events),
            )
        ]
        self.assertEqual(existences, [(src_path, True)])

    async def test_false_for_deletion(self) -> None:
        src_path = self.temporary_directory / 'a.suf'
        source_events: list[watchdog.events.FileSystemEvent] = [
            watchdog.events.FileDeletedEvent(str(src_path))
        ]
        existences: list[tuple[pathlib.Path, bool]] = [
            (path, existence) async for path, existence in
            phile.watchdog.asyncio.monitor_file_existence(
                directory_path=self.temporary_directory,
                expected_suffix='.suf',
                watchdog_view=to_async_iter(source_events),
            )
        ]
        self.assertEqual(existences, [(src_path, False)])

    async def test_returns_two_items_for_move(self) -> None:
        src_path = self.temporary_directory / 'a.suf'
        dest_path = self.temporary_directory / 'b.suf'
        source_events: list[watchdog.events.FileSystemEvent] = [
            watchdog.events.FileMovedEvent(
                str(src_path), str(dest_path)
            )
        ]
        existences: list[tuple[pathlib.Path, bool]] = [
            (path, existence) async for path, existence in
            phile.watchdog.asyncio.monitor_file_existence(
                directory_path=self.temporary_directory,
                expected_suffix='.suf',
                watchdog_view=to_async_iter(source_events),
            )
        ]
        self.assertEqual(
            existences, [(src_path, False), (dest_path, True)]
        )

    async def test_ignores_wrong_suffix(self) -> None:
        src_path = self.temporary_directory / 'a.suf_wrong'
        source_events: list[watchdog.events.FileSystemEvent] = [
            watchdog.events.FileCreatedEvent(str(src_path))
        ]
        existences: list[tuple[pathlib.Path, bool]] = [
            (path, existence) async for path, existence in
            phile.watchdog.asyncio.monitor_file_existence(
                directory_path=self.temporary_directory,
                expected_suffix='.suf',
                watchdog_view=to_async_iter(source_events),
            )
        ]
        self.assertEqual(existences, [])


class TestLoadChangedFiles(
    UsesObserver,
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.expected_files: (
            list[tuple[pathlib.Path, typing.Optional[str]]]
        )
        self.loader: collections.abc.AsyncIterator[tuple[
            pathlib.Path, typing.Optional[str]]]
        self.watchdog_view: collections.abc.AsyncIterator[
            watchdog.events.FileSystemEvent]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.expected_files = []
        self.watchdog_view = await self.schedule_watchdog_observer(
            self.temporary_directory
        )
        self.loader = phile.watchdog.asyncio.load_changed_files(
            directory_path=self.temporary_directory,
            expected_suffix='.suf',
            watchdog_view=self.watchdog_view,
        )

    async def assert_returns(self, ) -> None:
        received_files: (
            list[tuple[pathlib.Path, typing.Optional[str]]]
        ) = []
        try:
            load_aiter = self.loader.__aiter__()
            for expected_file in self.expected_files:
                found = False
                while not found:
                    received_file = await load_aiter.__anext__()
                    received_files.append(received_file)
                    found = (received_file == expected_file)
        except BaseException as error:
            message = (
                'Did not receive\n{expected_files}\n'
                'Received\n{received_files}'.format(
                    expected_files=self.expected_files,
                    received_files=received_files,
                )
            )
            raise self.failureException(message) from error

    async def test_loads_readable_file(self) -> None:
        self.expected_files.append(
            (self.temporary_directory / 'a.suf', 'b')
        )
        load_task = asyncio.create_task(self.assert_returns())
        await asyncio.sleep(0)  # Give the task time to start.
        self.expected_files[0][0].write_text('b')
        await phile.asyncio.wait_for(load_task)

    async def test_returns_none_for_deletion(self) -> None:
        await self.test_loads_readable_file()
        self.expected_files.clear()
        self.expected_files.append(
            (self.temporary_directory / 'a.suf', None)
        )
        load_task = asyncio.create_task(self.assert_returns())
        await asyncio.sleep(0)
        self.expected_files[0][0].unlink()
        await phile.asyncio.wait_for(load_task)

    async def test_ignores_wrong_suffix(self) -> None:
        self.expected_files.append(
            (self.temporary_directory / 'a.suf', 'b')
        )
        load_task = asyncio.create_task(self.assert_returns())
        await asyncio.sleep(0)
        (self.temporary_directory / 'b.suf_bad').write_text('no')
        self.expected_files[0][0].write_text('b')
        await phile.asyncio.wait_for(load_task)
