#!/usr/bin/env python3
"""
--------------------
Test :mod:`phile.os`
--------------------
"""

# Standard libraries.
import os
import unittest

# Internal packages.
import phile.os


class TestEnviron(unittest.TestCase):
    """Tests :class:`~phile.os.Environ`."""

    def setUp(self) -> None:
        self.key = 'phile'
        backup_value = os.environ.get(self.key)
        self.addCleanup(
            lambda: os.environ.pop(self.key, None)
            if (backup_value is None) else
            (os.environ.__setitem__(self.key, backup_value))
        )

    def test_set_changes_env_var(self) -> None:
        environ = phile.os.Environ()
        environ.set(phile='testing')
        self.assertEqual(os.environ[self.key], 'testing')
        environ.set(phile='still')
        self.assertEqual(os.environ[self.key], 'still')

    def test_restore_does_restore(self) -> None:
        os.environ[self.key] = 'testing'
        environ = phile.os.Environ()
        environ.set(phile='nested')
        self.assertEqual(os.environ[self.key], 'nested')
        environ.restore()
        self.assertEqual(os.environ[self.key], 'testing')
