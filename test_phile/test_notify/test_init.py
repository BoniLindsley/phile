#!/usr/bin/env python3

# Standard library.
import datetime
import typing
import unittest

# Internal packages.
import phile.notify


class TestEntry(unittest.TestCase):
    def test_construct_signatures(self) -> None:
        phile.notify.Entry(name="n")
        phile.notify.Entry(
            name="n",
            text="t",
            modified_at=datetime.datetime.now(),
        )

    def test_available_attributes(self) -> None:
        now = datetime.datetime.now()
        entry = phile.notify.Entry(
            name="n",
            text="t",
            modified_at=now,
        )
        self.assertEqual(entry.name, "n")
        self.assertEqual(entry.text, "t")
        self.assertEqual(entry.modified_at, now)

    def test_default_attributes(self) -> None:
        entry = phile.notify.Entry(name="n")
        self.assertEqual(entry.text, "")
        self.assertIsNone(entry.modified_at)


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.notify_registry: phile.notify.Registry
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.notify_registry = phile.notify.Registry()

    def test_invariants(self) -> None:
        current_keys = self.notify_registry.current_keys
        current_values = self.notify_registry.current_values
        self.assertEqual(current_keys, sorted(current_keys))
        self.assertEqual(
            current_keys, [entry.name for entry in current_values]
        )

    def test_set__with_new_entry_inserts(self) -> None:
        notify_entry = phile.notify.Entry(
            name="abc", text="c", modified_at=datetime.datetime.now()
        )
        self.notify_registry.add_entry(notify_entry)
        self.assertEqual(
            self.notify_registry.current_values, [notify_entry]
        )
        self.test_invariants()
