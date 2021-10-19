#!/usr/bin/env python3

# Standard libraries.
import asyncio
import contextlib
import collections.abc
import datetime
import pathlib
import typing
import unittest

# External dependencies.
import watchdog.events

# Internal dependencies.
import phile.asyncio
import phile.asyncio.pubsub
import phile.data
import phile.notify.watchdog
import phile.watchdog.asyncio
from test_phile.test_configuration.test_init import UsesConfiguration


def round_down_to_two_seconds(
    source: datetime.datetime,
) -> datetime.datetime:
    return source - datetime.timedelta(
        seconds=source.second % 2, microseconds=source.microsecond
    )


def round_up_to_two_seconds(
    source: datetime.datetime,
) -> datetime.datetime:
    return source + (
        datetime.timedelta(minutes=1)
        - datetime.timedelta(
            seconds=source.second, microseconds=source.microsecond
        )
    ) % datetime.timedelta(seconds=2)


class TimeInterval:
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        now = datetime.datetime.now()
        self.before = now
        self.after = now


def assert_entry_is(
    test_case: unittest.TestCase,
    entry: phile.notify.Entry,
    target_entry: phile.notify.Entry,
    modified_interval: TimeInterval,
) -> None:
    test_case.assertEqual(entry.name, target_entry.name)
    test_case.assertEqual(entry.text, target_entry.text)
    test_case.assertGreaterEqual(
        entry.modified_at,
        round_down_to_two_seconds(modified_interval.before),
    )
    test_case.assertLessEqual(
        entry.modified_at,
        round_up_to_two_seconds(modified_interval.after),
    )


@contextlib.contextmanager
def mark_time_interval() -> collections.abc.Iterator[TimeInterval]:
    time_interval = TimeInterval()
    try:
        yield time_interval
    finally:
        time_interval.after = datetime.datetime.now()


class TestGetDirectory(UsesConfiguration, unittest.TestCase):
    def test_returns_path(self) -> None:
        directory_path = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        self.assertIsInstance(directory_path, pathlib.Path)


class TestGetPath(UsesConfiguration, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.path = phile.notify.watchdog.get_path(
            name="n", configuration=self.configuration
        )

    def test_returns_path(self) -> None:
        self.assertIsInstance(self.path, pathlib.Path)

    def test_path_has_given_name(self) -> None:
        self.assertEqual(
            self.path.name.removesuffix(
                self.configuration.notify_suffix
            ),
            "n",
        )

    def test_path_in_get_directory(self) -> None:
        self.assertIn(
            phile.notify.watchdog.get_directory(
                configuration=self.configuration
            ),
            self.path.parents,
        )

    def test_path_has_correct_suffix(self) -> None:
        self.assertTrue(
            self.path.name.endswith(self.configuration.notify_suffix)
        )


class TestLoadFromPath(UsesConfiguration, unittest.TestCase):
    def test_reads_from_given_path(self) -> None:
        notify_name = "n"
        notify_text = "t"
        notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        notify_directory.mkdir()
        notify_path = phile.notify.watchdog.get_path(
            name=notify_name, configuration=self.configuration
        )
        with mark_time_interval() as created_between:
            notify_path.write_text(notify_text)
        notify_entry = phile.notify.watchdog.load_from_path(
            path=notify_path, configuration=self.configuration
        )
        assert_entry_is(
            test_case=self,
            entry=notify_entry,
            target_entry=phile.notify.Entry(
                name=notify_name, text=notify_text
            ),
            modified_interval=created_between,
        )


class TestLoad(UsesConfiguration, unittest.TestCase):
    def test_reads_from_given_path(self) -> None:
        notify_entry = phile.notify.Entry(name="n", text="t")
        notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        notify_directory.mkdir()
        notify_path = phile.notify.watchdog.get_path(
            name=notify_entry.name, configuration=self.configuration
        )
        with mark_time_interval() as created_between:
            notify_path.write_text(notify_entry.text)
        loaded_entry = phile.notify.watchdog.load(
            name=notify_entry.name, configuration=self.configuration
        )
        assert_entry_is(
            test_case=self,
            entry=loaded_entry,
            target_entry=notify_entry,
            modified_interval=created_between,
        )


class TestSave(UsesConfiguration, unittest.TestCase):
    def test_writes_inside_notify_directory(self) -> None:
        notify_entry = phile.notify.Entry(name="n", text="t")
        notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        notify_directory.mkdir()
        phile.notify.watchdog.save(
            entry=notify_entry, configuration=self.configuration
        )
        notify_path = phile.notify.watchdog.get_path(
            name=notify_entry.name, configuration=self.configuration
        )
        notify_text = notify_path.read_text()
        self.assertEqual(notify_text, notify_entry.text)


class TestTarget(UsesConfiguration, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = phile.notify.watchdog.Target(
            configuration=self.configuration
        )
        self.notify_entry = phile.notify.Entry(name="n", text="t")
        self.notify_path = phile.notify.watchdog.get_path(
            name=self.notify_entry.name,
            configuration=self.configuration,
        )

    def test_set__creates_file_if_missing(self) -> None:
        self.assertTrue(not self.notify_path.exists())
        self.target.set(entry=self.notify_entry)
        self.assertTrue(self.notify_path.exists())
        file_content = self.notify_path.read_text()
        self.assertEqual(file_content, self.notify_entry.text)

    def test_set__writes_to_file_if_exists(self) -> None:
        self.target.set(entry=self.notify_entry)
        self.notify_entry.text = "s"
        self.target.set(entry=self.notify_entry)
        file_content = self.notify_path.read_text()
        self.assertEqual(file_content, self.notify_entry.text)

    def test_pop__removes_file_if_exists(self) -> None:
        self.target.set(entry=self.notify_entry)
        self.target.pop(name=self.notify_entry.name)
        self.assertTrue(not self.notify_path.exists())

    def test_pop__ignores_if_missing(self) -> None:
        # Tests that it does not raise exceptions.
        self.target.pop(name=self.notify_entry.name)

    def test_close__pops_any_entries_set(self) -> None:
        self.target.set(entry=self.notify_entry)
        notify_entry_2 = phile.notify.Entry(name="m")
        self.target.set(entry=notify_entry_2)
        self.target.close()
        self.assertTrue(not self.notify_path.exists())
        notify_path_2 = phile.notify.watchdog.get_path(
            name=notify_entry_2.name, configuration=self.configuration
        )
        self.assertTrue(not notify_path_2.exists())

    def test_close__ignores_if_no_entries_set(self) -> None:
        # Tests that it does not raise exceptions.
        self.target.close()


class TestUpdatePath(
    UsesConfiguration, unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        super().setUp()
        self.notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        self.notify_directory.mkdir()
        self.notify_entry = phile.notify.Entry(name="n", text="c")
        self.notify_path = phile.notify.watchdog.get_path(
            name=self.notify_entry.name,
            configuration=self.configuration,
        )
        self.notify_registry = phile.notify.Registry()
        self.notify_view = self.notify_registry.event_queue.__aiter__()

    async def test_inserts_entry_if_unknown(self) -> None:
        with mark_time_interval() as created_between:
            phile.notify.watchdog.save(
                entry=self.notify_entry, configuration=self.configuration
            )
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(notify_event.type, phile.data.EventType.INSERT)
        self.assertEqual(notify_event.index, 0)
        self.assertEqual(notify_event.key, self.notify_entry.name)
        assert_entry_is(
            test_case=self,
            entry=notify_event.value,
            target_entry=self.notify_entry,
            modified_interval=created_between,
        )
        self.assertEqual(
            notify_event.current_keys, [self.notify_entry.name]
        )
        self.assertEqual(
            notify_event.current_values, [notify_event.value]
        )

    async def test_sets_entry_if_known(self) -> None:
        await self.test_inserts_entry_if_unknown()
        self.notify_entry.text = "d"
        with mark_time_interval() as created_between:
            phile.notify.watchdog.save(
                entry=self.notify_entry, configuration=self.configuration
            )
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(notify_event.type, phile.data.EventType.SET)
        self.assertEqual(notify_event.index, 0)
        self.assertEqual(notify_event.key, self.notify_entry.name)
        assert_entry_is(
            test_case=self,
            entry=notify_event.value,
            target_entry=self.notify_entry,
            modified_interval=created_between,
        )
        self.assertEqual(
            notify_event.current_keys, [self.notify_entry.name]
        )
        self.assertEqual(
            notify_event.current_values, [notify_event.value]
        )

    async def test_remvoes_missing_path_if_entry_known(self) -> None:
        await self.test_inserts_entry_if_unknown()
        self.notify_path.unlink()
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(notify_event.type, phile.data.EventType.DISCARD)
        self.assertEqual(notify_event.index, 0)
        self.assertEqual(notify_event.key, self.notify_entry.name)
        self.assertEqual(notify_event.current_keys, [])
        self.assertEqual(notify_event.current_values, [])

    async def test_ignores_mising_path_if_entry_unknown(self) -> None:
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        # If it was ignored,
        # then new insertion event would be received as expected.
        await self.test_inserts_entry_if_unknown()

    async def test_returns_true_if_path_was_found(self) -> None:
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        added = await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        self.assertTrue(added)

    async def test_returns_false_if_path_not_found(self) -> None:
        added = await phile.asyncio.wait_for(
            phile.notify.watchdog.update_path(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                path=self.notify_path,
            )
        )
        self.assertTrue(not added)


class TestUpdateExistingPaths(
    UsesConfiguration, unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        super().setUp()
        self.notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        self.notify_directory.mkdir()
        self.notify_entry = phile.notify.Entry(name="n", text="c")
        self.notify_path = phile.notify.watchdog.get_path(
            name=self.notify_entry.name,
            configuration=self.configuration,
        )
        self.notify_registry = phile.notify.Registry()
        self.notify_view = self.notify_registry.event_queue.__aiter__()

    async def test_inserts_entry_if_unknown(self) -> None:
        with mark_time_interval() as created_between:
            phile.notify.watchdog.save(
                entry=self.notify_entry, configuration=self.configuration
            )
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_existing_paths(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
            )
        )
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(notify_event.type, phile.data.EventType.INSERT)
        self.assertEqual(notify_event.index, 0)
        self.assertEqual(notify_event.key, self.notify_entry.name)
        assert_entry_is(
            test_case=self,
            entry=notify_event.value,
            target_entry=self.notify_entry,
            modified_interval=created_between,
        )
        self.assertEqual(
            notify_event.current_keys, [self.notify_entry.name]
        )
        self.assertEqual(
            notify_event.current_values, [notify_event.value]
        )

    async def test_insert_more_entries_if_found(self) -> None:
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        self.notify_entry.name = "m"
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_existing_paths(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
            )
        )
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(len(notify_event.current_keys), 1)
        notify_event = await phile.asyncio.wait_for(
            self.notify_view.__anext__()
        )
        self.assertEqual(len(notify_event.current_keys), 2)

    async def test_returns_paths_added(self) -> None:
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        entry_2 = phile.notify.Entry(name="p")
        path_2 = phile.notify.watchdog.get_path(
            name=entry_2.name, configuration=self.configuration
        )
        phile.notify.watchdog.save(
            entry=entry_2, configuration=self.configuration
        )
        added_paths = await phile.asyncio.wait_for(
            phile.notify.watchdog.update_existing_paths(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
            )
        )
        self.assertEqual(added_paths, {self.notify_path, path_2})

    async def test_ignores_directory(self) -> None:
        self.notify_path.mkdir()
        await phile.asyncio.wait_for(
            phile.notify.watchdog.update_existing_paths(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
            )
        )
        self.notify_path.rmdir()
        # Test that it really was ignored.
        await self.test_inserts_entry_if_unknown()


class TestProcessWatchdogView(
    UsesConfiguration, unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        super().setUp()
        self.notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        self.notify_directory.mkdir()
        self.notify_entry = phile.notify.Entry(name="n", text="c")
        self.notify_path = phile.notify.watchdog.get_path(
            name=self.notify_entry.name,
            configuration=self.configuration,
        )
        self.notify_registry = phile.notify.Registry()
        self.notify_view = self.notify_registry.event_queue.__aiter__()
        self.ready = asyncio.Event()
        self.watchdog_queue = phile.asyncio.pubsub.Queue[
            watchdog.events.FileSystemEvent
        ]()
        self.watchdog_view = self.watchdog_queue.__aiter__()

    async def test_exit_invariant(self) -> None:
        # Discards added entries on exit.
        self.assertEqual(self.notify_registry.current_keys, [])

    async def test_gracefully_stop_if_watchdog_queue_done(self) -> None:
        self.watchdog_queue.put_done()
        await phile.asyncio.wait_for(
            phile.notify.watchdog.process_watchdog_view(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                ready=self.ready,
                watchdog_view=self.watchdog_view,
            )
        )
        await self.test_exit_invariant()

    async def test_updates_existing_paths(self) -> None:
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        self.watchdog_queue.put(
            watchdog.events.FileCreatedEvent(str(self.notify_path))
        )
        self.watchdog_queue.put_done()
        await phile.asyncio.wait_for(
            phile.notify.watchdog.process_watchdog_view(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                ready=self.ready,
                watchdog_view=self.watchdog_view,
            )
        )
        await self.test_exit_invariant()

    async def test_updates_new_paths(self) -> None:
        worker_task = asyncio.create_task(
            phile.notify.watchdog.process_watchdog_view(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                ready=self.ready,
                watchdog_view=self.watchdog_view,
            )
        )
        await phile.asyncio.wait_for(self.ready.wait())
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        self.watchdog_queue.put(
            watchdog.events.FileCreatedEvent(str(self.notify_path))
        )
        self.watchdog_queue.put_done()
        await phile.asyncio.wait_for(worker_task)
        await self.test_exit_invariant()

    async def test_updates_deleted_paths(self) -> None:
        phile.notify.watchdog.save(
            entry=self.notify_entry, configuration=self.configuration
        )
        self.watchdog_queue.put(
            watchdog.events.FileCreatedEvent(str(self.notify_path))
        )
        worker_task = asyncio.create_task(
            phile.notify.watchdog.process_watchdog_view(
                configuration=self.configuration,
                notify_registry=self.notify_registry,
                ready=self.ready,
                watchdog_view=self.watchdog_view,
            )
        )
        self.notify_path.unlink()
        self.watchdog_queue.put(
            watchdog.events.FileDeletedEvent(str(self.notify_path))
        )
        self.watchdog_queue.put_done()
        await phile.asyncio.wait_for(worker_task)
        await self.test_exit_invariant()


class TestAsyncOpen(UsesConfiguration, unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.observer = phile.watchdog.asyncio.Observer()
        self.notify_directory = phile.notify.watchdog.get_directory(
            configuration=self.configuration
        )
        self.notify_directory.mkdir()
        self.notify_registry = phile.notify.Registry()

    async def test_async_cm_returns_target(self) -> None:
        async_cm = phile.notify.watchdog.async_open(
            configuration=self.configuration,
            notify_registry=self.notify_registry,
            observer=self.observer,
        )
        # Pylint does not know it is an async CM?
        notify_target = await phile.asyncio.wait_for(
            async_cm.__aenter__()  # pylint: disable=no-member
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            async_cm.__aexit__(  # pylint: disable=no-member
                None,
                None,
                None,
            ),
        )
        self.assertIsInstance(
            notify_target, phile.notify.watchdog.Target
        )
