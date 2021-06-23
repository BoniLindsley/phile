#!/usr/bin/env python3

# Standard libraries.
import unittest

# Internal packages.
import phile.capability


class TestAlreadyEnabled(unittest.TestCase):

    def test_check_is_runtime_error(self) -> None:
        self.assertIsInstance(
            phile.capability.AlreadyEnabled(), RuntimeError
        )


class TestRegistry(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()

    def test_getitem_non_existent(self) -> None:
        self.assertIsNone(self.capability_registry.get(int))

    def test_getitem_setitem(self) -> None:
        self.capability_registry[int] = 1
        self.assertEqual(self.capability_registry[int], 1)

    def test_set(self) -> None:
        self.capability_registry.set(2)
        self.assertEqual(self.capability_registry[int], 2)

    def test_provide_returns_context_manager_for_clean_up(self) -> None:
        with self.capability_registry.provide(1):
            self.assertIn(int, self.capability_registry)
            self.assertEqual(self.capability_registry[int], 1)
        self.assertNotIn(int, self.capability_registry)

    def test_provide_allows_specified_capability(self) -> None:
        value = phile.capability.AlreadyEnabled()
        with self.capability_registry.provide(value, RuntimeError):
            self.assertIn(RuntimeError, self.capability_registry)
            self.assertEqual(
                self.capability_registry[RuntimeError], value
            )
        self.assertNotIn(RuntimeError, self.capability_registry)

    def test_provide_raises_if_already_provided(self) -> None:
        self.capability_registry[int] = 0
        with self.assertRaises(phile.capability.AlreadyEnabled):
            with self.capability_registry.provide(1):
                pass
        self.assertEqual(self.capability_registry[int], 0)
