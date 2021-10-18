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
import phile.launcher
import phile.main
from test_phile.test_PySide2.test_QtCore import UsesPySide2


class TestRun(unittest.TestCase):
    def test_runs_given_target(self) -> None:
        async def target(
            launcher_registry: phile.launcher.Registry,
        ) -> None:
            del launcher_registry
            await asyncio.sleep(0)

        phile.main.run(target)

    def test_stopping_loop_forces_exit(self) -> None:
        async def target(
            launcher_registry: phile.launcher.Registry,
        ) -> None:
            del launcher_registry
            asyncio.get_running_loop().stop()
            await asyncio.sleep(0)

        with self.assertRaises(asyncio.CancelledError):
            phile.main.run(target)


class TestRunWithPySide2(UsesPySide2, unittest.IsolatedAsyncioTestCase):
    def test_has_launcher_that_creates_qapplication(self) -> None:
        async def target(
            launcher_registry: phile.launcher.Registry,
        ) -> None:
            # pylint: disable=import-outside-toplevel
            await phile.asyncio.wait_for(
                launcher_registry.state_machine.start("pyside2")
            )
            import PySide2.QtWidgets

            self.assertIn(
                PySide2.QtWidgets.QApplication,
                launcher_registry.capability_registry,
            )

        phile.main.run(target)
