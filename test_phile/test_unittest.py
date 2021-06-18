#!/usr/bin/env python3

# Standard libraries.
import pathlib
import unittest

# Internal modules.
import phile.unittest


class TestUsesTemporaryDirectory(
    phile.unittest.UsesTemporaryDirectory, unittest.TestCase
):

    def test_available_attributes(self) -> None:
        self.assertIsInstance(self.temporary_directory, pathlib.Path)

    def test_directory_is_directory(self) -> None:
        self.assertTrue(self.temporary_directory.is_dir())

    def test_directory_is_writable(self) -> None:
        file_path = self.temporary_directory / 'file.name'
        file_path.touch()
        self.assertTrue(file_path.is_file())
