#!/usr/bin/env python3
"""
-----------------
Test :mod:`phile`
-----------------
"""

# Standard libraries
import phile
import unittest


class TestCapabilities(unittest.TestCase):
    """Tests :class:`~phile.Capabilities`."""

    def test_set(self) -> None:
        capabilities = phile.Capabilities()
        capabilities['number'] = 1

    def test_get(self) -> None:
        capabilities = phile.Capabilities()
        capabilities['number'] = 1
        self.assertEqual(capabilities.get('number'), 1)

    def test_get_non_existent(self) -> None:
        capabilities = phile.Capabilities()
        self.assertIsNone(capabilities.get('number'))
