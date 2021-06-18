#!/usr/bin/env python3

# Standard libraries.
import pathlib
import tempfile
import typing
import unittest


class UsesTemporaryDirectory(unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.temporary_directory: pathlib.Path
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        super().setUp()
        directory = (  # pylint: disable=consider-using-with
            tempfile.TemporaryDirectory()
        )
        self.addCleanup(directory.cleanup)
        self.temporary_directory = pathlib.Path(directory.name)
