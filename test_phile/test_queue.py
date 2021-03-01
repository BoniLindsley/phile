#!/usr/bin/env python3
"""
-----------------------
Test :mod:`phile.queue`
-----------------------
"""

# Standard library.
import unittest

# Internal packages.
import phile.queue


class TestIterableSimpleQueue(unittest.TestCase):
    """Tests :func:`~phile.queue.IterableSimpleQueue`."""

    def test_is_iteratable(self) -> None:
        queue = phile.queue.IterableSimpleQueue[int]()
        queue.put(8)
        queue.put(5)
        queue.put(3)
        queue.put(2)
        self.assertEqual(
            # Force use of `__iter__`.
            # pragma pylint: disable=unnecessary-comprehension
            [number for number in queue],
            [8, 5, 3, 2]
        )
