#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.launcher.defaults`
-----------------------------------
"""

# Standard libraries.
import unittest

# Internal packages.
import phile.launcher.defaults
from test_phile.test_launcher.test_init import (
    UsesRegistry as UsesLauncherRegistry
)


class TestAddKeyring(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_keyring`."""

    def test_keyring_added(self) -> None:
        phile.launcher.defaults.add_keyring(
            capability_registry=self.capability_registry
        )
        self.assertTrue(
            self.launcher_registry.database.contains('keyring')
        )
