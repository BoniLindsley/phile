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
        phile.tray.Entry(name="n")
        phile.tray.Entry(
            name="n",
            icon_name="i",
            icon_path=pathlib.Path("p"),
            text_icon="t",
        )

    def test_available_attributes(self) -> None:
        entry = phile.tray.Entry(
            name="n",
            icon_name="i",
            icon_path=pathlib.Path("p"),
            text_icon="t",
        )
        self.assertEqual(entry.name, "n")
        self.assertEqual(entry.icon_name, "i")
        self.assertEqual(entry.icon_path, pathlib.Path("p"))
        self.assertEqual(entry.text_icon, "t")

    def test_default_attributes(self) -> None:
        entry = phile.tray.Entry(name="n")
        self.assertEqual(entry.name, "n")
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
                    Entry(name="1", text_icon="Tray"),
                    Entry(name="2", text_icon="Entries"),
                    Entry(name="3", text_icon="To"),
                    Entry(name="4", text_icon="Tray"),
                    Entry(name="5", text_icon="Text"),
                ]
            ),
            "TrayEntriesToTrayText",
        )


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.tray_registry: phile.tray.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_registry = phile.tray.Registry()

    def test_invariants(self) -> None:
        current_keys = self.tray_registry.current_keys
        current_values = self.tray_registry.current_values
        self.assertEqual(current_keys, sorted(current_keys))
        self.assertEqual(
            current_keys, [entry.name for entry in current_values]
        )

    def test_set__with_new_entry_inserts(self) -> None:
        tray_entry = phile.tray.Entry(name="abc")
        self.tray_registry.add_entry(tray_entry)
        self.assertEqual(self.tray_registry.current_values, [tray_entry])
        self.test_invariants()


class TestTextIcons(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.text_icons: phile.tray.TextIcons
        self.tray_registry: phile.tray.Registry

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
        self.tray_registry.add_entry(
            phile.tray.Entry(name="n", text_icon="abc")
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(full_text, "abc")

    async def test_set_entry_updates_current_value(self) -> None:
        event_view = self.text_icons.event_queue.__aiter__()
        self.tray_registry.add_entry(
            phile.tray.Entry(name="n", text_icon="abc")
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(self.text_icons.current_value, full_text)

    async def test_set_entry_text_to_same_value_is_ignored(self) -> None:
        event_view = self.text_icons.event_queue.__aiter__()
        self.tray_registry.add_entry(
            phile.tray.Entry(name="n", text_icon="abc")
        )
        full_text = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(full_text, "abc")
        self.tray_registry.add_entry(
            phile.tray.Entry(name="n", icon_name="i", text_icon="abc")
        )
        await phile.asyncio.wait_for(self.text_icons.aclose())
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_aclose_ends_event_queue(self) -> None:
        await phile.asyncio.wait_for(self.text_icons.aclose())
        event_view = self.text_icons.event_queue.__aiter__()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())
