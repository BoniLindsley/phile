#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.tray.tray_file`
--------------------------------
"""

# Standard library.
import functools
import pathlib
import tempfile
import typing
import unittest

# Internal packages.
import phile
import phile.asyncio
import phile.configuration
import phile.watchdog.asyncio
import phile.pubsub_event
import phile.tray
from test_phile.test_configuration.test_init import (
    PreparesEntries as PreparesConfigurationEntries
)


class TestFileCheckPath(unittest.TestCase):
    """Tests :meth:`~phile.tray.File.check_path`."""

    def set_up_configuration(self) -> None:
        tray_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(tray_directory.cleanup)
        self.configuration = configuration = (
            phile.Configuration(
                tray_directory=pathlib.Path(tray_directory.name),
                tray_suffix='.tt'
            )
        )
        self.tray_directory = (configuration.tray_directory)
        self.tray_suffix = configuration.tray_suffix

    def set_up_path_filter(self) -> None:
        self.path_filter = functools.partial(
            phile.tray.File.check_path, configuration=self.configuration
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_path_filter()

    def test_match(self) -> None:
        """Check an explicit path that should pass."""
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name
        self.assertTrue(
            phile.tray.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_partial_for_filter(self) -> None:
        """
        Usable as a single parameter callback
        using :func:`~functools.partial`.
        """
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name
        self.assertTrue(self.path_filter(path))

    def test_make_path_result(self) -> None:
        """Result of :meth:`~phile.tray.File.make_path` should pass."""
        path_stem = 'stem'
        path = phile.tray.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_directory_mismatch(self) -> None:
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name / name
        self.assertTrue(not self.path_filter(path))

    def test_suffix_mismatch(self) -> None:
        name = 'name' + self.tray_suffix + '_not'
        path = self.tray_directory / name
        self.assertTrue(not self.path_filter(path))


class TestFile(unittest.TestCase):
    """Tests :class:`~phile.tray.File`."""

    def setUp(self) -> None:
        """
        Create a directory to use as a tray directory.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        tray_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(tray_directory.cleanup)
        self.tray_directory_path = pathlib.Path(tray_directory.name)
        self.configuration = phile.Configuration(
            tray_directory=self.tray_directory_path
        )
        self.name = 'clock'
        self.path = self.configuration.tray_directory / (
            self.name + self.configuration.tray_suffix
        )
        self.tray = phile.tray.File(path=self.path)

    def test_construct_with_path(self) -> None:
        """Constructing with just path should be possible."""
        tray = phile.tray.File(self.path)
        self.assertEqual(tray.path, self.path)

    def test_load(self) -> None:
        """Parse a tray file for information."""
        data = {
            'icon_name': 'phile-tray',
            'icon_path': self.tray_directory_path / 'phile-tray-read',
            'text_icon': 'N',
        }
        content = '{text_icon}\n{{'
        content += '"icon_name": "{icon_name}"'
        content += ',"icon_path": "{icon_path}"'
        content += '}}'
        content = content.format(**data)
        self.tray.path.write_text(content)
        self.assertTrue(self.tray.load())
        self.assertEqual(self.tray.icon_name, data['icon_name'])
        self.assertEqual(self.tray.icon_path, data['icon_path'])
        self.assertEqual(self.tray.text_icon, data['text_icon'])

    def test_load_fails_decoading(self) -> None:
        """Load returns false if JSON decoding fails.."""
        self.tray.path.write_text('\nA\n')
        self.assertTrue(not self.tray.load())

    def test_save(self) -> None:
        """Save a tray file with some information."""
        data = {
            'icon_name': 'phile-tray',
            'text_icon': 'N',
        }
        expected_content = '{text_icon}\n{{'
        expected_content += '"icon_name": "{icon_name}"'
        expected_content += '}}'
        expected_content = expected_content.format(**data)
        self.tray.icon_name = data['icon_name']
        self.tray.text_icon = data['text_icon']
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertEqual(content, expected_content)

    def test_save_nothing(self) -> None:
        """Savea blank tray file. It should still have a new line."""
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertTrue(not content)


class TestFilesToText(unittest.TestCase):
    """Tests :func:`~phile.tray.files_to_text`."""

    def test_merge(self) -> None:
        File = phile.tray.File
        self.assertEqual(
            phile.tray.files_to_text(
                files=[
                    File(path=pathlib.Path(), text_icon='Tray'),
                    File(path=pathlib.Path(), text_icon='Files'),
                    File(path=pathlib.Path(), text_icon='To'),
                    File(path=pathlib.Path(), text_icon='Tray'),
                    File(path=pathlib.Path(), text_icon='Text'),
                ]
            ), 'TrayFilesToTrayText'
        )


class TestEventType(unittest.TestCase):

    def test_members_exist(self) -> None:
        members = {
            phile.tray.EventType.INSERT,
            phile.tray.EventType.POP,
            phile.tray.EventType.SET,
        }
        self.assertEqual(len(members), 3)


class TestEvent(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.tray_directory_path: pathlib.Path
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        tray_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(tray_directory.cleanup)
        self.tray_directory_path = pathlib.Path(tray_directory.name)

    def test_initialisation(self) -> None:
        phile.tray.Event(
            type=phile.tray.EventType.INSERT,
            index=0,
            changed_entry=phile.tray.Entry(self.tray_directory_path),
            current_entries=[],
        )

    def test_members(self) -> None:
        entry = phile.tray.Entry(self.tray_directory_path / 'x')
        event = phile.tray.Event(
            type=phile.tray.EventType.POP,
            index=1,
            changed_entry=entry,
            current_entries=[entry],
        )
        self.assertEqual(event.type, phile.tray.EventType.POP)
        self.assertEqual(event.index, 1)
        self.assertEqual(event.changed_entry, entry)
        self.assertEqual(event.current_entries, [entry])


class TestRegistry(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.subscriber: phile.pubsub_event.Subscriber[phile.tray.Event]
        self.tray_directory_path: pathlib.Path
        self.tray_entry: phile.tray.Entry
        self.tray_path: pathlib.Path
        self.tray_registry: phile.tray.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        tray_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(tray_directory.cleanup)
        self.tray_directory_path = pathlib.Path(tray_directory.name)
        self.tray_path = self.tray_directory_path / 't.t'
        self.tray_entry = phile.tray.Entry(
            self.tray_directory_path / 't.t',
        )
        self.tray_registry = phile.tray.Registry()
        self.subscriber = phile.pubsub_event.Subscriber(
            publisher=self.tray_registry.event_publisher,
        )

    def test_default_initialisable(self) -> None:
        self.assertIsInstance(self.tray_registry, phile.tray.Registry)

    def test_has_attributes(self) -> None:
        self.assertIsInstance(
            self.tray_registry.event_publisher,
            phile.pubsub_event.Publisher,
        )
        self.assertEqual(
            self.tray_registry.current_entries,
            list[phile.tray.Entry](),
        )

    def test_update_new_entry(self) -> None:
        self.tray_path.write_text('abc')
        self.tray_registry.update(self.tray_path)
        self.assertEqual(
            self.tray_registry.current_entries,
            [self.tray_entry],
        )
        self.assertEqual(
            phile.tray.files_to_text(self.tray_registry.current_entries),
            'abc',
        )

    async def test_publishes_new_entry(self) -> None:
        self.test_update_new_entry()
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[self.tray_entry],
            )
        )

    def test_update_extra_entry(self) -> None:
        self.test_update_new_entry()
        tray_path = self.tray_directory_path / 't2.t'
        tray_path.write_text('def')
        self.tray_registry.update(tray_path)
        self.assertEqual(
            self.tray_registry.current_entries,
            [
                self.tray_entry,
                phile.tray.Entry(tray_path),
            ],
        )
        self.assertEqual(
            phile.tray.files_to_text(self.tray_registry.current_entries),
            'abcdef',
        )

    async def test_publishes_extra_entry(self) -> None:
        self.test_update_extra_entry()
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[self.tray_entry],
            ),
        )
        tray_entry = phile.tray.Entry(self.tray_directory_path / 't2.t')
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=1,
                changed_entry=tray_entry,
                current_entries=[self.tray_entry, tray_entry],
            ),
        )

    def test_update_old_entry(self) -> None:
        self.test_update_new_entry()
        self.tray_path.write_text('def')
        self.tray_registry.update(self.tray_path)
        self.assertEqual(
            self.tray_registry.current_entries,
            [self.tray_entry],
        )
        self.assertEqual(
            phile.tray.files_to_text(self.tray_registry.current_entries),
            'def',
        )

    async def test_publishes_old_entry(self) -> None:
        self.test_update_old_entry()
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[self.tray_entry],
            )
        )
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.SET,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[self.tray_entry],
            )
        )

    def test_update_deleted_entry(self) -> None:
        self.test_update_new_entry()
        self.tray_path.unlink()
        self.tray_registry.update(self.tray_path)
        self.assertEqual(self.tray_registry.current_entries, [])
        self.assertEqual(
            phile.tray.files_to_text(self.tray_registry.current_entries),
            '',
        )

    async def test_publishes_deleted_entry(self) -> None:
        self.test_update_deleted_entry()
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[self.tray_entry],
            )
        )
        event = await phile.asyncio.wait_for(self.subscriber.pull())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.POP,
                index=0,
                changed_entry=self.tray_entry,
                current_entries=[],
            )
        )

    def test_update_ignores_missing_entry(self) -> None:
        self.tray_registry.update(self.tray_path)
        self.assertEqual(self.tray_registry.current_entries, [])
        self.assertEqual(
            phile.tray.files_to_text(self.tray_registry.current_entries),
            '',
        )


class TestProvideRegistry(
    PreparesConfigurationEntries,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.configuration: phile.configuration.Entries
        self.observer: phile.watchdog.asyncio.Observer
        self.subscriber: phile.pubsub_event.Subscriber[phile.tray.Event]
        self.tray_directory: pathlib.Path
        self.tray_entry: phile.tray.Entry
        self.tray_path: pathlib.Path

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.configuration = phile.configuration.load()
        self.observer = phile.watchdog.asyncio.Observer()
        self.tray_directory = (
            self.configuration.state_directory_path /
            self.configuration.tray_directory
        )
        self.tray_directory.mkdir()
        self.tray_path = self.tray_directory / (
            't' + self.configuration.tray_suffix
        )
        self.tray_entry = phile.tray.Entry(self.tray_path)

    async def wait_for_event(
        self, expected_event: phile.tray.Event
    ) -> None:
        while True:
            event = await phile.asyncio.wait_for(self.subscriber.pull())
            if event == expected_event:
                return

    async def test_context_exit_stops_publisher(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
        with self.assertRaises(phile.pubsub_event.NoMoreMessages):
            await phile.asyncio.wait_for(self.subscriber.pull())

    async def test_create_entry(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )

    async def test_create_two_entries(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.SET,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )
            tray_path_2 = self.tray_directory / (
                't2' + self.configuration.tray_suffix
            )
            tray_path_2.write_text('def')
            tray_entry_2 = phile.tray.Entry(tray_path_2)
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=1,
                    changed_entry=tray_entry_2,
                    current_entries=[self.tray_entry, tray_entry_2],
                )
            )

    async def test_modify_entry(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )
            self.tray_path.write_text('def')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.SET,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )

    async def test_delete_entry(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )
            self.tray_path.unlink()
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.POP,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[],
                )
            )

    async def test_move_entry(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )
            tray_path_2 = self.tray_directory / (
                't2' + self.configuration.tray_suffix
            )
            self.tray_path.rename(tray_path_2)
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.POP,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[],
                )
            )
            tray_entry_2 = phile.tray.Entry(tray_path_2)
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=tray_entry_2,
                    current_entries=[tray_entry_2],
                )
            )

    async def test_ignores_wrong_suffix(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            wrong_tray_path = self.tray_directory / (
                'wrong' + self.configuration.tray_suffix + '_s'
            )
            wrong_tray_path.write_text('abc')
            # We test this by trying to get an event
            # that shoudl nto be ignored.
            # Cannot test with exiting context manager
            # because of race condition
            # between detecting file change and the exit.
            self.tray_path.write_text('abc')
            event = await phile.asyncio.wait_for(self.subscriber.pull())
            self.assertEqual(
                event,
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )

    async def test_ignore_wrong_moved_to_entry(self) -> None:
        async with phile.tray.provide_registry(
            configuration=self.configuration, observer=self.observer
        ) as tray_registry:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            self.tray_path.write_text('abc')
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )
            tray_path_2 = self.tray_directory / (
                't2' + self.configuration.tray_suffix + '_wrong'
            )
            self.tray_path.rename(tray_path_2)
            await self.wait_for_event(
                phile.tray.Event(
                    type=phile.tray.EventType.POP,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[],
                )
            )
            # Ensure the moved-to target is ignored
            # by checking for new events.
            self.tray_path.write_text('abc')
            event = await phile.asyncio.wait_for(self.subscriber.pull())
            self.assertEqual(
                event,
                phile.tray.Event(
                    type=phile.tray.EventType.INSERT,
                    index=0,
                    changed_entry=self.tray_entry,
                    current_entries=[self.tray_entry],
                )
            )


class TestFullTextPublisher(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.publisher = phile.tray.FullTextPublisher()

    def test_attributes_exist(self) -> None:
        self.assertEqual(self.publisher.current_value, '')

    def test_push_records_pushed_message(self) -> None:
        self.publisher.push('abc')
        self.assertEqual(self.publisher.current_value, 'abc')


class TestProvideFullText(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.subscriber: phile.pubsub_event.Subscriber[str]
        self.tray_directory_path: pathlib.Path
        self.tray_path: pathlib.Path
        self.tray_registry: phile.tray.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        tray_directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(tray_directory.cleanup)
        self.tray_directory_path = pathlib.Path(tray_directory.name)
        self.tray_path = self.tray_directory_path / 't.t'
        self.tray_registry = phile.tray.Registry()

    async def test_context_exit_stops_publisher(self) -> None:
        async with phile.tray.provide_full_text(
            tray_registry=self.tray_registry,
        ) as full_text_publisher:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=full_text_publisher,
            )
        with self.assertRaises(phile.pubsub_event.NoMoreMessages):
            await phile.asyncio.wait_for(self.subscriber.pull())

    async def test_new_file(self) -> None:
        async with phile.tray.provide_full_text(
            tray_registry=self.tray_registry
        ) as full_text_publisher:
            self.subscriber = phile.pubsub_event.Subscriber(
                publisher=full_text_publisher,
            )
            self.tray_path.write_text('abc\n{}')
            self.tray_registry.update(self.tray_path)
            new_text = await phile.asyncio.wait_for(
                self.subscriber.pull()
            )
            self.assertTrue(new_text, 'abc')


if __name__ == '__main__':
    unittest.main()
