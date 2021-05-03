#!/usr/bin/env python3
"""
----------------------
Test :mod:`phile.main`
----------------------
"""

# Standard library.
import asyncio
import unittest

# Internal packages.
import phile.asyncio
import phile.capability
import phile.launcher
import phile.main
from test_phile.test_PySide2.test_QtCore import UsesPySide2


class TestRun(unittest.TestCase):
    """Tests :func:`~phile.main.run`."""

    def test_runs_given_target(self) -> None:

        async def target(
            _capability_registry: phile.capability.Registry,
        ) -> None:
            await asyncio.sleep(0)

        phile.main.run(target)

    def test_stopping_loop_forces_exit(self) -> None:

        async def target(
            _capability_registry: phile.capability.Registry,
        ) -> None:
            asyncio.get_running_loop().stop()
            await asyncio.sleep(0)

        with self.assertRaises(asyncio.CancelledError):
            phile.main.run(target)


class TestRunWithPySide2(UsesPySide2, unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.main.run` with PySide2 launcher."""

    def test_has_launcher_that_creates_qapplication(self) -> None:

        async def target(
            capability_registry: phile.capability.Registry,
        ) -> None:
            # pylint: disable=import-outside-toplevel
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
            await phile.asyncio.wait_for(
                launcher_registry.start('pyside2')
            )
            import PySide2.QtWidgets
            self.assertIn(
                PySide2.QtWidgets.QApplication, capability_registry
            )

            qapplication = (
                capability_registry[PySide2.QtWidgets.QApplication]
            )
            self.addCleanup(qapplication.shutdown)
            self.addCleanup(
                phile.PySide2.QtCore.process_deferred_delete_events
            )
            self.addCleanup(phile.PySide2.QtCore.process_events)

        phile.main.run(target)
