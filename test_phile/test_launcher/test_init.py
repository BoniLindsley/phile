#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.launcher`
--------------------------
"""

# Standard libraries.
import asyncio
import dataclasses
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.launcher


class TestNameInUse(unittest.TestCase):
    """Tests :func:`~phile.launcher.NameInUse`."""

    def test_check_is_runtime_error(self) -> None:
        self.assertIsInstance(phile.launcher.NameInUse(), RuntimeError)


async def noop() -> None:
    pass


@dataclasses.dataclass
class Counter:
    value: int


def create_awaiter(limit: int) -> tuple[Counter, phile.launcher.Command]:
    counter = Counter(value=0)

    async def awaiter() -> None:
        for _ in range(limit):
            counter.value += 1
            await asyncio.sleep(0)

    return counter, awaiter


class TestDatabase(unittest.TestCase):
    """Tests :func:`~phile.launcher.Database`."""

    def setUp(self) -> None:
        super().setUp()
        self.launcher_database = phile.launcher.Database()

    def test_contains_on_empty_database(self) -> None:
        self.assertFalse(self.launcher_database.contains('not_there'))

    def test_add_with_minimal_data(self) -> None:
        self.launcher_database.add('minimal', {'exec_start': [noop]})

    def test_add_fails_if_name_already_added(self) -> None:
        name = 'reused'
        self.launcher_database.add(name, {'exec_start': [noop]})
        with self.assertRaises(phile.launcher.NameInUse):
            self.launcher_database.add(name, {'exec_start': [noop]})

    def test_contains_after_add(self) -> None:
        name = 'checked'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.assertTrue(self.launcher_database.contains(name))

    def test_add_fails_without_exec_start(self) -> None:
        with self.assertRaises(phile.launcher.MissingDescriptorData):
            self.launcher_database.add('no_exec_start', {})

    def test_add_binds_to_creates_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent',
            {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            },
        )
        self.launcher_database.add(
            'bind_target',
            {'exec_start': [noop]},
        )
        self.assertEqual(
            self.launcher_database.binds_to['dependent'],
            {'bind_target'},
        )
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent'},
        )

    def test_add_binds_to_adds_to_existing_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent_1', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1'},
        )
        self.launcher_database.add(
            'dependent_2', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1', 'dependent_2'},
        )

    def test_remove(self) -> None:
        name = 'to_be_removed'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.launcher_database.remove(name)

    def test_is_contains_after_remove(self) -> None:
        name = 'unchecked'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.launcher_database.remove(name)
        self.assertFalse(self.launcher_database.contains(name))

    def test_remove_ignores_if_not_added(self) -> None:
        self.launcher_database.remove('not_added_unit')

    def test_remove_unbinds_from_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent_1', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add(
            'dependent_2', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1', 'dependent_2'},
        )
        self.launcher_database.remove('dependent_1')
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_2'},
        )

    def test_remove_removes_bound_by_if_it_empties(self) -> None:
        self.launcher_database.add(
            'dependent', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent'},
        )
        self.launcher_database.remove('dependent')
        self.assertNotIn('bind_target', self.launcher_database.bound_by)
