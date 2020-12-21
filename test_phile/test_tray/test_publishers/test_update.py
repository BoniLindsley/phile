#!/usr/bin/env python3
"""
----------------------------------------
Test :mod:`phile.tray.publishers.update`
----------------------------------------
"""

# Standard library.
import asyncio
import datetime
import unittest
import unittest.mock

# Internal packages.
import phile.tray.publishers.update


class TestTarget(unittest.TestCase):

    def static_test_target_is_context_manager(
        self, target: phile.tray.publishers.update.Target
    ) -> None:
        with target:
            pass

    def static_test_target_returns_callable(
        self, target: phile.tray.publishers.update.Target
    ) -> None:
        with target as update:
            update().total_seconds()


class TestSelfTarget(unittest.TestCase):

    def setUp(self) -> None:
        self.target = phile.tray.publishers.update.SelfTarget()

    def test_context_target_is_self(self) -> None:
        entered = False
        with self.assertRaises(NotImplementedError):
            with self.target as update:
                self.assertTrue(update, self.target)
                entered = True
        self.assertTrue(entered)

    def test_is_abstract_callable(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.target()


class TestSleepLoop(unittest.TestCase):

    def setUp(self) -> None:
        self.target = target = unittest.mock.MagicMock(
            return_value=datetime.timedelta(seconds=1)
        )
        self.loop = phile.tray.publishers.update.sleep_loop(target)

    def test_can_be_cancelled(self) -> None:
        with unittest.mock.patch(
            'asyncio.sleep',
            side_effect=[unittest.mock.DEFAULT, asyncio.CancelledError]
        ) as sleep_mock, self.assertRaises(asyncio.CancelledError):
            asyncio.run(self.loop)
            sleep_mock.assert_called_once_with(1)

    def test_calls_target(self) -> None:
        with unittest.mock.patch(
            'asyncio.sleep',
            side_effect=[unittest.mock.DEFAULT, asyncio.CancelledError]
        ) as sleep_mock, self.assertRaises(asyncio.CancelledError):
            asyncio.run(self.loop)
            self.target.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
