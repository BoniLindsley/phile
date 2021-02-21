#!/usr/bin/env python3
"""
-----------------------------
Test :mod:`phile.trigger.cli`
-----------------------------
"""

# Standard library.
import argparse
import io
import pathlib
import tempfile
import unittest

# Internal packages.
import phile
import phile.trigger.cli


class TestIterableSimpleQueue(unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.IterableSimpleQueue`."""

    def test_is_iteratable(self) -> None:
        queue = phile.trigger.cli.IterableSimpleQueue[int]()
        queue.put(8)
        queue.put(5)
        queue.put(3)
        queue.put(2)
        # Force use of `__iter__`.
        self.assertEqual([number for number in queue], [8, 5, 3, 2])


class TestCache(unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.Cache`."""

    def setUp(self) -> None:
        super().setUp()
        trigger_directory = tempfile.TemporaryDirectory()
        self.addCleanup(trigger_directory.cleanup)
        self.trigger_root = pathlib.Path(trigger_directory.name)
        self.trigger_suffix = '.t'
        self.cache = phile.trigger.cli.Cache(
            trigger_root=self.trigger_root,
            trigger_suffix=self.trigger_suffix,
        )
        self.set_up_triggers()

    def set_up_triggers(self) -> None:
        put = self.cache.expired_triggers.put
        trigger_root = self.cache.trigger_root
        self.missing_trigger = trigger_root / 'missing.t'
        put(self.missing_trigger)
        self.new_trigger = trigger_root / 'new.t'
        self.new_trigger.touch()
        put(self.new_trigger)
        self.cache.update_expired()

    def test_refresh_resets_and_orders_id_by_filename(self) -> None:
        self.missing_trigger.touch()
        self.new_trigger.unlink(missing_ok=True)
        self.extra_trigger = self.trigger_root / 'extra.t'
        self.extra_trigger.touch()
        self.cache.refresh()
        self.assertEqual(
            self.cache.available_triggers,
            {self.extra_trigger, self.missing_trigger}
        )
        self.assertEqual(
            self.cache.known_triggers, {
                1: self.extra_trigger,
                2: self.missing_trigger
            }
        )
        self.assertEqual(
            self.cache.trigger_ids, {
                self.extra_trigger: 1,
                self.missing_trigger: 2
            }
        )
        self.assertEqual(self.cache.next_new_id, 3)

    def test_refresh_empty_trigger_root(self) -> None:
        self.new_trigger.unlink(missing_ok=True)
        self.cache.refresh()
        self.assertFalse(self.cache.available_triggers)
        self.assertFalse(self.cache.known_triggers)
        self.assertFalse(self.cache.trigger_ids)
        self.assertEqual(self.cache.next_new_id, 1)

    def test_execute_removes_trigger_file(self) -> None:
        self.cache.execute([2])
        self.assertFalse(self.new_trigger.exists())

    def test_execute_empty_list_is_okay(self) -> None:
        self.cache.execute([])

    def test_update_expired_checks_expired_existence(self) -> None:
        # Also checks that `expired_triggers` has ordered `put`.
        self.assertEqual(
            self.cache.available_triggers, {self.new_trigger}
        )
        self.assertEqual(
            self.cache.known_triggers, {
                1: self.missing_trigger,
                2: self.new_trigger
            }
        )
        self.assertEqual(
            self.cache.trigger_ids, {
                self.missing_trigger: 1,
                self.new_trigger: 2
            }
        )
        self.assertEqual(self.cache.next_new_id, 3)

    def test_assign_ids_ignores_known_triggers(self) -> None:
        self.cache.assign_ids([self.new_trigger])
        self.assertEqual(self.cache.known_triggers[2], self.new_trigger)
        self.assertEqual(self.cache.trigger_ids[self.new_trigger], 2)
        self.assertEqual(self.cache.next_new_id, 3)

    def test_purge_clears_all_data(self) -> None:
        self.cache.purge()
        self.assertFalse(self.cache.available_triggers)
        self.assertFalse(self.cache.known_triggers)
        self.assertFalse(self.cache.trigger_ids)
        self.assertEqual(self.cache.next_new_id, 1)

    def test_to_name_removes_trigger_root(self) -> None:
        to_name = self.cache.to_name
        trigger_root = self.trigger_root
        self.assertEqual(to_name(trigger_root / 'a.t'), 'a.t')
        self.assertEqual(to_name(trigger_root / 'd' / 'a.t'), 'd/a.t')

    def test_is_trigger_checks_parents_and_suffix(self) -> None:
        is_trigger = self.cache.is_trigger
        trigger_root = self.trigger_root
        self.assertTrue(is_trigger(trigger_root / 'a.t'))
        self.assertTrue(is_trigger(trigger_root / 'd' / 'a.t'))
        self.assertFalse(is_trigger(trigger_root / 'wrong.suffix'))
        self.assertFalse(
            is_trigger(pathlib.Path(str(trigger_root) + 'wrong_root'))
        )


class TestPrompt(unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.Prompt`."""

    def setUp(self) -> None:
        super().setUp()
        trigger_directory = tempfile.TemporaryDirectory()
        self.addCleanup(trigger_directory.cleanup)
        self.trigger_root = pathlib.Path(trigger_directory.name)
        self.trigger_suffix = '.t'
        self.cache = phile.trigger.cli.Cache(
            trigger_root=self.trigger_root,
            trigger_suffix=self.trigger_suffix,
        )
        self.stdout = io.StringIO()
        self.prompt = phile.trigger.cli.Prompt(
            cache=self.cache, stdout=self.stdout
        )
        self.prompt.use_rawinput = False
        self.set_up_triggers()

    def set_up_triggers(self) -> None:
        self.missing_trigger = self.trigger_root / 'missing.t'
        self.cache.expired_triggers.put(self.missing_trigger)
        self.new_trigger = self.trigger_root / 'new.t'
        self.new_trigger.touch()
        self.cache.expired_triggers.put(self.new_trigger)

    def test_do_EOF_stops_prompt(self) -> None:
        self.assertTrue(self.prompt.onecmd('EOF'))

    def test_do_refresh(self) -> None:
        self.assertFalse(self.prompt.onecmd('refresh'))
        self.assertEqual(
            self.cache.available_triggers, {self.new_trigger}
        )
        self.assertEqual(
            self.cache.known_triggers, {1: self.new_trigger}
        )
        self.assertEqual(self.cache.trigger_ids, {self.new_trigger: 1})
        self.assertEqual(self.cache.next_new_id, 2)

    def test_do_exe(self) -> None:
        self.assertFalse(self.prompt.onecmd('exe 2'))
        self.assertFalse(self.new_trigger.exists())

    def test_do_execute_warns_wrong_argument(self) -> None:
        self.assertFalse(self.prompt.onecmd('exe a'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unable to parse trigger id.'
            ' invalid literal for int() with base 10: \'a\''
        )

    def test_do_list(self) -> None:
        self.assertFalse(self.prompt.onecmd('list'))
        self.assertEqual(self.stdout.getvalue(), '2 new.t\n')

    def test_do_list_all(self) -> None:
        self.assertFalse(self.prompt.onecmd('list_all'))
        self.assertEqual(
            self.stdout.getvalue(), '1 missing.t\n2 new.t\n'
        )
