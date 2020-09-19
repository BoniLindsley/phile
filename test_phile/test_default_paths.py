#!/usr/bin/env python3

# Standard libraries.
import pathlib
import unittest

# External dependencies.
import appdirs  # type: ignore

# Internal packages.
import phile.default_paths


class TestDataPaths(unittest.TestCase):
    """
    Unit test for :mod:`phile.default_paths`.
    """

    def __init__(self, *args, **kwargs):
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def test_required_paths(self):
        """Make sure paths that we use are given as paths."""
        path_type = type(pathlib.Path())
        self.assertEqual(
            type(phile.default_paths.notification_directory), path_type
        )


if __name__ == '__main__':
    unittest.main()
