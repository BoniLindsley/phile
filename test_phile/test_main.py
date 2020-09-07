#!/usr/bin/env python3

# Standard library.
import unittest

# Own packages.
import phile.__main__


class TestMain(unittest.TestCase):
    """
    Unit test for :func:`main`.
    """

    def __init__(self, *args, **kwargs):
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def test_call_success(self):
        """Make sure the call returns 0."""
        argv = ['phile']
        self.assertEqual(phile.__main__.main(argv), 0)


if __name__ == '__main__':
    unittest.main()
