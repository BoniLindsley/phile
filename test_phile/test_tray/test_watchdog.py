#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.tray.tray_file`
--------------------------------
"""

# Standard library.
import asyncio
import json
import pathlib
import typing
import unittest

# External dependencies.
import watchdog.events
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.asyncio.pubsub
import phile.configuration
import phile.watchdog.asyncio
import phile.tray
import phile.tray.watchdog
import phile.unittest
from test_phile.test_configuration.test_init import UsesConfiguration


class TestLoad(phile.unittest.UsesTemporaryDirectory, unittest.TestCase):

    def test_uses_path_stem_as_name(self) -> None:
        tray_path = self.temporary_directory / 'n.t'
        tray_path.write_text('a')
        loaded_entry = phile.tray.watchdog.load(
            path=tray_path, tray_suffix='.t'
        )
        self.assertEqual(loaded_entry.name, 'n')

    def test_allows_empty_suffix(self) -> None:
        tray_path = self.temporary_directory / 'n.t'
        tray_path.write_text('a')
        loaded_entry = phile.tray.watchdog.load(
            path=tray_path, tray_suffix=''
        )
        self.assertEqual(loaded_entry.name, 'n.t')

    def test_warns_if_tray_suffix_not_found(self) -> None:
        tray_path = self.temporary_directory / ('n.t')
        tray_path.write_text('a')
        with self.assertWarns(UserWarning):
            loaded_entry = phile.tray.watchdog.load(
                path=tray_path, tray_suffix='.bad'
            )
        self.assertEqual(loaded_entry.name, 'n.t')

    def test_loads_json_data(self) -> None:
        content = 'N\n{"icon_name": "phile-tray", "icon_path": "p"}'
        tray_path = self.temporary_directory / 'n'
        tray_path.write_text(content)
        loaded_entry = phile.tray.watchdog.load(
            path=tray_path, tray_suffix=''
        )
        self.assertEqual(
            loaded_entry,
            phile.tray.Entry(
                name='n',
                icon_name='phile-tray',
                icon_path=pathlib.Path('p'),
                text_icon='N',
            ),
        )

    def test_icon_path_is_optional(self) -> None:
        # Most data is optional. This option is done for coverage.
        content = 'N\n{"icon_name": "phile-tray"}'
        tray_path = self.temporary_directory / 'n'
        tray_path.write_text(content)
        loaded_entry = phile.tray.watchdog.load(
            path=tray_path, tray_suffix=''
        )
        self.assertEqual(
            loaded_entry,
            phile.tray.Entry(
                name='n',
                icon_name='phile-tray',
                text_icon='N',
            ),
        )

    def test_raises_if_file_missing(self) -> None:
        tray_path = self.temporary_directory / 'n.t'
        with self.assertRaises(FileNotFoundError):
            phile.tray.watchdog.load(path=tray_path, tray_suffix='.t')

    def test_raises_if_decoding_fails(self) -> None:
        tray_path = self.temporary_directory / 'n.t'
        tray_path.write_text('\nA\n')
        with self.assertRaises(json.decoder.JSONDecodeError):
            phile.tray.watchdog.load(path=tray_path, tray_suffix='.t')


class TestSave(phile.unittest.UsesTemporaryDirectory, unittest.TestCase):

    def test_writes_json_data(self) -> None:
        entry_to_save = phile.tray.Entry(
            name='n',
            icon_name='i',
            icon_path=pathlib.Path('p'),
            text_icon='N',
        )
        phile.tray.watchdog.save(
            entry=entry_to_save,
            tray_directory=self.temporary_directory,
            tray_suffix='.t',
        )
        tray_path = self.temporary_directory / 'n.t'
        saved_content = tray_path.read_text()
        self.assertEqual(
            saved_content,
            'N\n{"icon_name": "i", "icon_path": "p"}',
        )

    def test_empty_entry_gives_empty_file(self) -> None:
        entry_to_save = phile.tray.Entry(name='n')
        phile.tray.watchdog.save(
            entry=entry_to_save,
            tray_directory=self.temporary_directory,
            tray_suffix='.t',
        )
        tray_path = self.temporary_directory / 'n.t'
        saved_content = tray_path.read_text()
        self.assertEqual(saved_content, '')


class TestTarget(UsesConfiguration, unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.tray_directory: pathlib.Path

    def setUp(self) -> None:
        super().setUp()
        self.configuration.tray_suffix = '.tr'
        self.tray_directory = (
            self.configuration.state_directory_path /
            self.configuration.tray_directory
        )
        self.tray_directory.mkdir()

    def test_set__creates_file(self) -> None:
        new_entry = phile.tray.Entry(name='a')
        target = phile.tray.watchdog.Target(
            configuration=self.configuration,
        )
        target.set(new_entry)
        tray_file_path = self.tray_directory / 'a.tr'
        self.assertTrue(tray_file_path.exists())

    def test_pop__removes_file(self) -> None:
        tray_file_path = self.tray_directory / 'a.tr'
        tray_file_path.touch()
        target = phile.tray.watchdog.Target(
            configuration=self.configuration,
        )
        target.pop('a')
        self.assertTrue(not tray_file_path.exists())

    def test_pop__ignores_missing_file(self) -> None:
        target = phile.tray.watchdog.Target(
            configuration=self.configuration,
        )
        target.pop('a')

    def test_close__removes_set_trays(self) -> None:
        new_entry = phile.tray.Entry(name='a')
        target = phile.tray.watchdog.Target(
            configuration=self.configuration,
        )
        target.set(new_entry)
        target.close()
        tray_file_path = self.tray_directory / 'a.tr'
        self.assertTrue(not tray_file_path.exists())


class TestSource(
    phile.unittest.UsesTemporaryDirectory,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.tray_registry: phile.tray.Registry
        self.tray_source: phile.tray.watchdog.Source
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_registry = tray_registry = phile.tray.Registry()
        self.tray_source = phile.tray.watchdog.Source(
            tray_registry=tray_registry,
            tray_suffix='.tr',
        )

    async def test_process_path__sets_given_entry(self) -> None:
        tray_path = self.temporary_directory / 'n.tr'
        tray_path.touch()
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_path(path=tray_path)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        expected_entry = phile.tray.Entry(name='n', text_icon='')
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=expected_entry,
                current_entries=[expected_entry],
            )
        )

    async def test_process_path__ignores_wrong_suffix(self) -> None:
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_path(
            path=self.temporary_directory / 'n.t'
        )
        self.tray_registry.close()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_process_path__ignores_missing_file(self) -> None:
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_path(
            path=self.temporary_directory / 'n.tr'
        )
        self.tray_registry.close()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_process_path__ignores_ill_formed_file(self) -> None:
        tray_path = self.temporary_directory / 'n.tr'
        tray_path.write_text('\n?')
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_path(path=tray_path)
        self.tray_registry.close()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_process_watchdog_event__sets_given_entry(
        self
    ) -> None:
        tray_path = self.temporary_directory / 'n.tr'
        tray_path.touch()
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_watchdog_event(
            event=watchdog.events.FileCreatedEvent(
                src_path=str(tray_path)
            )
        )
        event = await phile.asyncio.wait_for(event_view.__anext__())
        expected_entry = phile.tray.Entry(name='n', text_icon='')
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=expected_entry,
                current_entries=[expected_entry],
            )
        )

    async def test_process_watchdog_event__process_moved_to_path(
        self
    ) -> None:
        tray_path = self.temporary_directory / 'n.tr'
        tray_path.touch()
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_watchdog_event(
            event=watchdog.events.FileMovedEvent(
                src_path=str(self.temporary_directory / 'm.tr'),
                dest_path=str(tray_path),
            )
        )
        expected_entry = phile.tray.Entry(name='n', text_icon='')

        async def assert_contains(
            expected_event: phile.tray.Event
        ) -> None:
            received_events: list[phile.tray.Event] = []

            async def run() -> None:
                async for event in event_view:
                    if event == expected_event:
                        return
                    received_events.append(event)

            try:
                await phile.asyncio.wait_for(run())
            except BaseException as error:
                message = (
                    'Expected:\n{expected_event}\n'
                    'Received:\n{received_events}'.format(
                        expected_event=expected_event,
                        received_events=received_events[0],
                    )
                )
                raise self.failureException(message) from error

        await assert_contains(
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=expected_entry,
                current_entries=[expected_entry],
            )
        )

    async def test_process_watchdog_event__ignores_directory_events(
        self
    ) -> None:
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_source.process_watchdog_event(
            event=watchdog.events.DirCreatedEvent(
                src_path=str(self.temporary_directory)
            )
        )
        self.tray_registry.close()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_process_watchdog_event_view(self) -> None:
        watchdog_event_queue = phile.watchdog.asyncio.EventQueue()
        process = asyncio.create_task(
            self.tray_source.process_watchdog_event_view(
                event_view=watchdog_event_queue.__aiter__(),
            )
        )
        self.addAsyncCleanup(phile.asyncio.cancel_and_wait, process)
        tray_path = self.temporary_directory / 'n.tr'
        tray_path.touch()
        tray_path_2 = self.temporary_directory / 'p.tr'
        tray_path_2.touch()
        watch = watchdog.observers.api.ObservedWatch(
            path=str(self.temporary_directory),
            recursive=False,
        )
        watchdog_event_queue.put(
            event_data=(
                watchdog.events.FileCreatedEvent(
                    src_path=str(tray_path)
                ),
                watch,
            )
        )
        watchdog_event_queue.put(
            event_data=(
                watchdog.events.FileCreatedEvent(
                    src_path=str(tray_path_2)
                ),
                watch,
            )
        )
        event_view = self.tray_registry.event_queue.__aiter__()
        event = await phile.asyncio.wait_for(event_view.__anext__())
        expected_entry = phile.tray.Entry(name='n', text_icon='')
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=expected_entry,
                current_entries=[expected_entry],
            )
        )
        event_2 = await phile.asyncio.wait_for(event_view.__anext__())
        expected_entry_2 = phile.tray.Entry(name='p', text_icon='')
        self.assertEqual(
            event_2,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=1,
                changed_entry=expected_entry_2,
                current_entries=[expected_entry, expected_entry_2],
            )
        )
        self.tray_registry.close()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())


class TestAsyncOpen(
    UsesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.observer: phile.watchdog.asyncio.Observer
        self.tray_directory: pathlib.Path
        self.tray_registry: phile.tray.Registry
        self.tray_event_view: phile.asyncio.pubsub.View[phile.tray.Event]
        self.tray_source: phile.tray.watchdog.Source

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.observer = phile.watchdog.asyncio.Observer()
        self.tray_directory = tray_directory = (
            self.configuration.state_directory_path /
            self.configuration.tray_directory
        )
        tray_directory.mkdir()
        self.tray_registry = phile.tray.Registry()
        self.tray_event_view = self.tray_registry.event_queue.__aiter__()
        async_open_cm = phile.tray.watchdog.async_open(
            configuration=self.configuration,
            observer=self.observer,
            tray_registry=self.tray_registry,
        )
        # Pylint does not know it is an async CM?
        self.tray_source = await phile.asyncio.wait_for(
            async_open_cm.__aenter__()  # pylint: disable=no-member
        )
        self.addAsyncCleanup(
            async_open_cm.__aexit__,  # pylint: disable=no-member
            None,
            None,
            None,
        )

    async def wait_for_event(
        self, expected_event: phile.tray.Event
    ) -> None:

        async def wait() -> None:
            async for event in self.tray_event_view:
                if event == expected_event:
                    break

        await phile.asyncio.wait_for(wait())

    async def test_detects_file_creation(self) -> None:
        tray_path = self.tray_directory / 'n.tray'
        tray_path.touch()
        tray_path_2 = self.tray_directory / 'p.tray'
        tray_path_2.touch()
        expected_entry = phile.tray.Entry(name='n', text_icon='')
        await self.wait_for_event(
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=expected_entry,
                current_entries=[expected_entry],
            )
        )
        expected_entry_2 = phile.tray.Entry(name='p', text_icon='')
        await self.wait_for_event(
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=1,
                changed_entry=expected_entry_2,
                current_entries=[expected_entry, expected_entry_2],
            )
        )
