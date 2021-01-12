#!/usr/bin/env python3

# Standard libraries.
import datetime
import unittest

# Internal packages.
import phile.datetime


class TestTimedeltaToSeconds(unittest.TestCase):
    """Tests :class:`~phile.datetime.timedelta_to_seconds`."""

    def test_converts_to_seconds(self) -> None:
        self.assertEqual(
            phile.datetime.timedelta_to_seconds(
                datetime.timedelta(minutes=1)
            ), 60
        )

    def test_none_to_none(self) -> None:
        self.assertIsNone(phile.datetime.timedelta_to_seconds(None))
