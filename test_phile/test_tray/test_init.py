#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.tray.tray_file`
--------------------------------
"""

# Standard library.
import pathlib
import typing
import unittest

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub
import phile.tray


class TestEntry(unittest.TestCase):

    def test_construct_signatures(self) -> None:
        phile.tray.Entry(name='n')
        phile.tray.Entry(
            name='n',
            icon_name='i',
            icon_path=pathlib.Path('p'),
            text_icon='t',
        )

    def test_available_attributes(self) -> None:
        entry = phile.tray.Entry(
            name='n',
            icon_name='i',
            icon_path=pathlib.Path('p'),
            text_icon='t',
        )
        self.assertEqual(entry.name, 'n')
        self.assertEqual(entry.icon_name, 'i')
        self.assertEqual(entry.icon_path, pathlib.Path('p'))
        self.assertEqual(entry.text_icon, 't')

    def test_default_attributes(self) -> None:
        entry = phile.tray.Entry(name='n')
        self.assertEqual(entry.name, 'n')
        self.assertIsNone(entry.icon_name)
        self.assertIsNone(entry.icon_path)
        self.assertIsNone(entry.text_icon)


class TestEntriesToText(unittest.TestCase):
    """Tests :func:`~phile.tray.entries_to_text`."""

    def test_merge(self) -> None:
        Entry = phile.tray.Entry
        self.assertEqual(
            phile.tray.entries_to_text(
                entries=[
                    Entry(name='1', text_icon='Tray'),
                    Entry(name='2', text_icon='Entries'),
                    Entry(name='3', text_icon='To'),
                    Entry(name='4', text_icon='Tray'),
                    Entry(name='5', text_icon='Text'),
                ]
            ), 'TrayEntriesToTrayText'
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

    def test_initialisation(self) -> None:
        phile.tray.Event(
            type=phile.tray.EventType.POP,
            index=0,
            changed_entry=phile.tray.Entry(name='n'),
            current_entries=[],
        )

    def test_members(self) -> None:
        entry = phile.tray.Entry(name='x')
        event = phile.tray.Event(
            type=phile.tray.EventType.SET,
            index=0,
            changed_entry=entry,
            current_entries=[entry],
        )
        self.assertEqual(event.type, phile.tray.EventType.SET)
        self.assertEqual(event.index, 0)
        self.assertEqual(event.changed_entry, entry)
        self.assertEqual(event.current_entries, [entry])


class TestRegistry(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.tray_registry: phile.tray.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_registry = phile.tray.Registry()

    def test_default_initialisable(self) -> None:
        self.assertIsInstance(self.tray_registry, phile.tray.Registry)

    def test_has_attributes(self) -> None:
        self.assertIsInstance(
            self.tray_registry.event_queue,
            phile.asyncio.pubsub.Queue,
        )
        self.assertEqual(
            self.tray_registry.current_entries,
            list[phile.tray.Entry](),
        )
        self.assertEqual(
            self.tray_registry.current_names,
            list[phile.tray.Entry](),
        )

    def test_current_names_is_cache_of_current_entry_names(self) -> None:
        self.assertEqual(
            self.tray_registry.current_names,
            [entry.name for entry in self.tray_registry.current_entries],
        )

    def test_current_names_is_sorted_and_so_is_current_entries(
        self
    ) -> None:
        self.assertEqual(
            self.tray_registry.current_names,
            sorted(self.tray_registry.current_names),
        )

    def test_current_names_invariants(self) -> None:
        self.test_current_names_is_cache_of_current_entry_names()
        self.test_current_names_is_sorted_and_so_is_current_entries()

    def test_set_new_entry_inserts(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        self.assertEqual(
            self.tray_registry.current_entries, [tray_entry]
        )
        self.test_current_names_invariants()

    async def test_set_new_entry_emits_events(self) -> None:
        event_view = self.tray_registry.event_queue.__aiter__()
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=0,
                changed_entry=tray_entry,
                current_entries=[tray_entry],
            )
        )

    def test_set_another_entry_inserts(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        another_entry = phile.tray.Entry(name='def')
        self.tray_registry.set(another_entry)
        self.assertEqual(
            self.tray_registry.current_entries,
            [tray_entry, another_entry]
        )
        self.test_current_names_invariants()

    def test_set_another_entry_with_smaller_name_inserts(self) -> None:
        tray_entry = phile.tray.Entry(name='def')
        self.tray_registry.set(tray_entry)
        another_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(another_entry)
        self.assertEqual(
            self.tray_registry.current_entries,
            [another_entry, tray_entry]
        )
        self.test_current_names_invariants()

    async def test_set_another_entry_emits_with_correct_index(
        self
    ) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        event_view = self.tray_registry.event_queue.__aiter__()
        another_entry = phile.tray.Entry(name='def')
        self.tray_registry.set(another_entry)
        self.assertEqual(
            self.tray_registry.current_entries,
            [tray_entry, another_entry]
        )
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=1,
                changed_entry=another_entry,
                current_entries=[tray_entry, another_entry],
            )
        )

    def test_set_existing_entry_updates(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        tray_entry.text_icon = 'n'
        self.tray_registry.set(tray_entry)
        self.assertEqual(
            self.tray_registry.current_entries, [tray_entry]
        )
        self.test_current_names_invariants()

    async def test_set_existing_entry_emits_event(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        event_view = self.tray_registry.event_queue.__aiter__()
        tray_entry.text_icon = 'n'
        self.tray_registry.set(tray_entry)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.SET,
                index=0,
                changed_entry=tray_entry,
                current_entries=[tray_entry],
            )
        )

    async def test_set_same_entry_does_not_emit_event(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_registry.set(tray_entry)
        # Test that no event was emitted by doing something
        # that would emit another event.
        another_entry = phile.tray.Entry(name=tray_entry.name + 'd')
        self.tray_registry.set(another_entry)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.INSERT,
                index=1,
                changed_entry=another_entry,
                current_entries=[tray_entry, another_entry],
            )
        )

    def test_pop_entry_removes(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        another_entry = phile.tray.Entry(name='def')
        self.tray_registry.set(another_entry)
        self.tray_registry.pop(tray_entry.name)
        self.assertEqual(
            self.tray_registry.current_entries, [another_entry]
        )
        self.test_current_names_invariants()

    def test_pop_last_entry_clears(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        self.tray_registry.pop(tray_entry.name)
        self.assertEqual(self.tray_registry.current_entries, [])
        self.test_current_names_invariants()

    def test_pop_unknown_entry_ignored(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        another_entry = phile.tray.Entry(name='def')
        self.tray_registry.pop(another_entry.name)
        self.assertEqual(
            self.tray_registry.current_entries, [tray_entry]
        )
        self.test_current_names_invariants()

    def test_pop_unknown_entry_ignored_even_if_name_is_not_at_end(
        self
    ) -> None:
        tray_entry = phile.tray.Entry(name='def')
        self.tray_registry.set(tray_entry)
        another_entry = phile.tray.Entry(name='abc')
        self.tray_registry.pop(another_entry.name)
        self.assertEqual(
            self.tray_registry.current_entries, [tray_entry]
        )
        self.test_current_names_invariants()

    async def test_pop_entry_emits_event(self) -> None:
        tray_entry = phile.tray.Entry(name='abc')
        self.tray_registry.set(tray_entry)
        event_view = self.tray_registry.event_queue.__aiter__()
        self.tray_registry.pop(tray_entry.name)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.tray.Event(
                type=phile.tray.EventType.POP,
                index=0,
                changed_entry=tray_entry,
                current_entries=[],
            )
        )

    async def test_close_ends_event_queue(self) -> None:
        self.tray_registry.close()
        event_view = self.tray_registry.event_queue.__aiter__()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_warns_if_setting_after_close(self) -> None:
        self.tray_registry.close()
        with self.assertWarns(UserWarning):
            self.tray_registry.set(phile.tray.Entry(name='n'))


class TestTextIcons(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.text_icons: phile.tray.TextIcons
        self.tray_registry: phile.tray.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_registry = tray_registry = phile.tray.Registry()
        self.text_icons = phile.tray.TextIcons(
            tray_registry=tray_registry
        )

    def test_available_attributes(self) -> None:
        self.assertIsInstance(self.text_icons.current_value, str)
        self.assertIsInstance(
            self.text_icons.event_queue, phile.asyncio.pubsub.Queue
        )

    async def test_set_entry_emits_event(self) -> None:
        event_view = self.text_icons.event_queue.__aiter__()
        self.tray_registry.set(
            phile.tray.Entry(name='n', text_icon='abc')
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(full_text, 'abc')

    async def test_set_entry_updates_current_value(self) -> None:
        event_view = self.text_icons.event_queue.__aiter__()
        self.tray_registry.set(
            phile.tray.Entry(name='n', text_icon='abc')
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(self.text_icons.current_value, full_text)

    async def test_set_entry_text_to_same_value_is_ignored(self) -> None:
        event_view = self.text_icons.event_queue.__aiter__()
        self.tray_registry.set(
            phile.tray.Entry(name='n', text_icon='abc')
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(full_text, 'abc')
        self.tray_registry.set(
            phile.tray.Entry(name='n', icon_name='i', text_icon='abc')
        )
        await phile.asyncio.wait_for(self.text_icons.aclose())
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_aclose_ends_event_queue(self) -> None:
        await phile.asyncio.wait_for(self.text_icons.aclose())
        event_view = self.text_icons.event_queue.__aiter__()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())
