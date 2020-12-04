#!/usr/bin/env python3
"""
------------------------
Test :mod:`phile.notify`
------------------------

.. automodule:: test_phile.test_notify.test_cli
.. automodule:: test_phile.test_notify.test_gui
"""

# Standard library.
import dataclasses
import datetime
import functools
import pathlib
import tempfile
import unittest

# Internal packages.
import phile.configuration
import phile.data
import phile.notify


def round_down_to_two_seconds(
    source: datetime.datetime
) -> datetime.datetime:
    return source - datetime.timedelta(
        seconds=source.second % 2, microseconds=source.microsecond
    )


def round_up_to_two_seconds(
    source: datetime.datetime
) -> datetime.datetime:
    return source + (
        datetime.timedelta(minutes=1) - datetime.timedelta(
            seconds=source.second, microseconds=source.microsecond
        )
    ) % datetime.timedelta(seconds=2)


class TestFileCheckPath(unittest.TestCase):
    """Tests :meth:`~phile.notify.File.check_path`."""

    def set_up_configuration(self) -> None:
        notification_directory = tempfile.TemporaryDirectory()
        self.addCleanup(notification_directory.cleanup)
        self.configuration = configuration = (
            phile.configuration.Configuration(
                notification_directory=pathlib.Path(
                    notification_directory.name
                ),
                notification_suffix='.nn'
            )
        )
        self.notification_directory = (
            configuration.notification_directory
        )
        self.notification_suffix = configuration.notification_suffix

    def set_up_path_filter(self) -> None:
        self.path_filter = path_filter = functools.partial(
            phile.notify.File.check_path,
            configuration=self.configuration
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_path_filter()

    def test_match(self) -> None:
        """Check an explicit path that should pass."""
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name
        self.assertTrue(
            phile.notify.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_partial_for_filter(self) -> None:
        """
        Usable as a single parameter callback
        using :func:`~functools.partial`.
        """
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name
        self.assertTrue(self.path_filter(path))

    def test_make_path_result(self) -> None:
        """Result of :meth:`~phile.notify.File.make_path` should pass."""
        path_stem = 'stem'
        path = phile.notify.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_directory_mismatch(self) -> None:
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name / name
        self.assertTrue(not self.path_filter(path))

    def test_suffix_mismatch(self) -> None:
        name = 'name' + self.notification_suffix + '_not'
        path = self.notification_directory / name
        self.assertTrue(not self.path_filter(path))


class TestFile(unittest.TestCase):
    """Tests :data:`~phile.notify.File`."""

    def set_up_configuration(self) -> None:
        notification_directory = tempfile.TemporaryDirectory()
        self.addCleanup(notification_directory.cleanup)
        self.notification_directory_path = pathlib.Path(
            notification_directory.name
        )
        self.configuration = phile.configuration.Configuration(
            notification_directory=self.notification_directory_path
        )

    def test_inherited_init(self) -> None:
        """Has default and keyword initialisation."""
        file = phile.notify.File(path=pathlib.Path())
        self.assertTrue(hasattr(file, 'path'))
        self.assertTrue(hasattr(file, 'modified_at'))
        self.assertTrue(hasattr(file, 'text'))
        self.assertTrue(hasattr(file, 'title'))
        phile.notify.File(
            path=pathlib.Path('Great Title'),
            modified_at=datetime.datetime(year=2001, month=1, day=1),
            text='This is a big paragraph.',
        )

    def test_from_path_stem(self) -> None:
        """Create from configuration and path stem."""
        self.set_up_configuration()
        file = phile.notify.File.from_path_stem(
            'config',
            configuration=self.configuration,
        )
        self.assertTrue(
            phile.notify.File.check_path(
                configuration=self.configuration, path=file.path
            )
        )

    def test_from_path_stem_accpets_init_arguments(self) -> None:
        """Create from configuration, forwards argument to init."""
        self.set_up_configuration()
        text = 'from_path_stem'
        file = phile.notify.File.from_path_stem(
            configuration=self.configuration,
            path_stem='config',
            text=text,
        )
        self.assertEqual(file.text, text)

    def test_is_sortable_load_notify(self) -> None:
        """Satisfies :class:`~phile.data.SortableLoadData` protocol."""
        _: phile.data.SortableLoadData = phile.notify.File(
            path=pathlib.Path()
        )

    def test_compare(self) -> None:
        """Partial order uses :data:`~phile.notify.File.path`."""
        file_1 = phile.notify.File(
            path=pathlib.Path('a/b'),
            modified_at=datetime.datetime(year=2001, month=1, day=1),
            text='This is a big paragraph.',
        )
        file_2 = phile.notify.File(
            path=pathlib.Path('a/b'),
            modified_at=datetime.datetime(year=2002, month=2, day=2),
            text='This is a bigger paragraph.',
        )
        self.assertEqual(file_1, file_2)
        file_2.path = pathlib.Path('a/c')
        self.assertLess(file_1, file_2)
        file_1.path = pathlib.Path('b/a')
        self.assertLess(file_1, file_2)

    def test_title(self) -> None:
        """Title is path stem."""
        title = 'b'
        file = phile.notify.File(path=pathlib.Path('a') / (title + '.n'))
        self.assertEqual(file.title, title)
        title = 'a'
        file.title = title
        self.assertEqual(file.title, title)

    def test_title_for_path_without_suffix(self) -> None:
        """Title is path stem, even without path suffix."""
        title = 'b'
        file = phile.notify.File(path=pathlib.Path('a') / title)
        self.assertEqual(file.title, title)
        title = 'a'
        file.title = title
        self.assertEqual(file.title, title)

    def test_load(self) -> None:
        """Load retrieves file content and modified time."""
        self.set_up_configuration()
        text = 'Reminder.'
        path = self.configuration.notification_directory / 'b'
        # The largest resolution mentioned in Python3 docs
        # is two second for FAT32.
        before = round_down_to_two_seconds(datetime.datetime.now())
        path.write_text(text)
        after = round_up_to_two_seconds(datetime.datetime.now())
        file = phile.notify.File(path=path)
        self.assertTrue(file.load())
        self.assertEqual(file.text, text)
        self.assertLessEqual(file.modified_at, after)
        self.assertGreaterEqual(file.modified_at, before)

    def test_load_fails_if_missing(self) -> None:
        """Load fails but returns if file is missing."""
        self.set_up_configuration()
        name = 'missing'
        path = self.configuration.notification_directory / name
        file = phile.notify.File(path=path)
        self.assertTrue(not file.load())

    def test_load_fails_if_is_directory(self) -> None:
        """Load fails but returns file path resolves to a directory."""
        self.set_up_configuration()
        name = 'missing'
        path = self.configuration.notification_directory / name
        path.mkdir()
        file = phile.notify.File(path=path)
        self.assertTrue(not file.load())

    def test_save(self) -> None:
        """Save sets file content and modified time."""
        self.set_up_configuration()
        text = 'Reminder.'
        path = self.configuration.notification_directory / 'b'
        file = phile.notify.File(path=path, text=text)
        before = round_down_to_two_seconds(datetime.datetime.now())
        file.save()
        after = round_up_to_two_seconds(datetime.datetime.now())
        self.assertEqual(path.read_text(), text)
        self.assertLessEqual(file.modified_at, after)
        self.assertGreaterEqual(file.modified_at, before)


if __name__ == '__main__':
    unittest.main()
