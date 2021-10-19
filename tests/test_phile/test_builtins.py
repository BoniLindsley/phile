#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.builtins`
--------------------------
"""

# Standard libraries.
import sys
import typing
import unittest

# Internal modules.
import phile.builtins


class TestProvideItem(unittest.TestCase):
    def test_assigns_item(self) -> None:
        target_map: dict[int, int] = {}
        phile.builtins.provide_item(target_map, 0, 1)
        self.assertEqual(target_map[0], 1)

    def test_returns_context(self) -> None:
        target_map: dict[int, int] = {}
        with phile.builtins.provide_item(target_map, 0, 1):
            self.assertIn(0, target_map)
        self.assertNotIn(0, target_map)
