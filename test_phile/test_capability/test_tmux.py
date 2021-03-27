#!/usr/bin/env python3
"""
---------------------------------
Test :mod:`phile.capability.tmux`
---------------------------------
"""

# Standard libraries.
import unittest

# Internal packages.
import phile.capability
import phile.capability.asyncio
import phile.capability.tmux
import phile.os
from test_phile.test_tmux.test_init import UsesRunningTmuxServer


class TestIsAvailable(unittest.TestCase):
    """Tests :func:`~phile.capability.tmux.is_available`."""

    def test_checks_for_environment_variable(self) -> None:
        environ = phile.os.Environ()
        environ.set(TMUX='1234')
        self.assertTrue(phile.capability.tmux.is_available())
        environ.set(TMUX=None)
        self.assertFalse(phile.capability.tmux.is_available())


# TODO(BoniLindsley): Add time limit on test.
class TestProvideAsyncTmuxClient(
    UsesRunningTmuxServer, unittest.TestCase
):
    """Tests :func:`~phile.capability.tmux.provide_async_tmux_client`."""

    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()
        phile.capability.asyncio.provide(
            capability_registry=self.capability_registry
        )

    def test_returns_context_manager_for_clean_up(self) -> None:
        with phile.capability.tmux.provide_async_tmux_client(
            capability_registry=self.capability_registry
        ):
            loop = phile.capability.asyncio.get_instance(
                capability_registry=self.capability_registry
            )
            loop.call_soon_threadsafe(loop.stop)
            phile.capability.asyncio.run(
                capability_registry=self.capability_registry
            )
