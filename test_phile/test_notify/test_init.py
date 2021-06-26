#!/usr/bin/env python3
"""
------------------------
Test :mod:`phile.notify`
------------------------
"""

# Standard library.
import collections.abc
import datetime
import functools
import pathlib
import typing
import unittest

# Internal packages.
import phile.data
import phile.notify
from test_phile.test_configuration.test_init import UsesConfiguration


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


class TestFileCheckPath(UsesConfiguration, unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.notification_directory: pathlib.Path
        self.notification_suffix: str
        self.path_filter: collections.abc.Callable[[pathlib.Path], bool]

    def setUp(self) -> None:
        super().setUp()
        self.notification_directory = (
            self.configuration.state_directory_path /
            self.configuration.notification_directory
        )
        self.notification_suffix = self.configuration.notification_suffix
        self.path_filter = functools.partial(
            phile.notify.File.check_path,
            configuration=self.configuration
        )

    def test_check_path__that_passes(self) -> None:
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name
        self.assertTrue(
            phile.notify.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_check_path__is_a_filter_that_uses_configuration(
        self
    ) -> None:
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name
        self.assertTrue(self.path_filter(path))

    def test_make_path__return_value_passes_check_path(self) -> None:
        path_stem = 'stem'
        path = phile.notify.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_check_path__fails_if_wrong_directory(self) -> None:
        name = 'name' + self.notification_suffix
        path = self.notification_directory / name / name
        self.assertTrue(not self.path_filter(path))

    def test_check_path__fails_if_wrong_suffix(self) -> None:
        name = 'name' + self.notification_suffix + '_not'
        path = self.notification_directory / name
        self.assertTrue(not self.path_filter(path))


class TestFile(UsesConfiguration, unittest.TestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.notification_directory: pathlib.Path

    def setUp(self) -> None:
        super().setUp()
        self.notification_directory = (
            self.configuration.state_directory_path /
            self.configuration.notification_directory
        )

    def test_has_default_and_keyword_initialisation(self) -> None:
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

    def test_from_path_stem__create_from_config_and_stem(self) -> None:
        file = phile.notify.File.from_path_stem(
            'config',
            configuration=self.configuration,
        )
        self.assertTrue(
            phile.notify.File.check_path(
                configuration=self.configuration, path=file.path
            )
        )

    def test_from_path_stem__accepts_config_and_init_arguments(
        self
    ) -> None:
        text = 'from_path_stem'
        file = phile.notify.File.from_path_stem(
            configuration=self.configuration,
            path_stem='config',
            text=text,
        )
        self.assertEqual(file.text, text)

    def test_satisfies_sortable_load_data_protocol(self) -> None:
        _: phile.data.SortableLoadData = phile.notify.File(
            path=pathlib.Path()
        )

    def test_partial_order_using_path(self) -> None:
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

    def test_title_is_path_stem(self) -> None:
        title = 'b'
        file = phile.notify.File(path=pathlib.Path('a') / (title + '.n'))
        self.assertEqual(file.title, title)
        title = 'a'
        file.title = title
        self.assertEqual(file.title, title)

    def test_title_is_path_stem_even_without_suffix(self) -> None:
        title = 'b'
        file = phile.notify.File(path=pathlib.Path('a') / title)
        self.assertEqual(file.title, title)
        title = 'a'
        file.title = title
        self.assertEqual(file.title, title)

    def test_load_retrieves_file_content_and_modified_time(self) -> None:
        text = 'Reminder.'
        self.notification_directory.mkdir()
        path = self.notification_directory / 'b'
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
        name = 'missing'
        path = self.notification_directory / name
        file = phile.notify.File(path=path)
        self.assertTrue(not file.load())

    def test_load_fails_if_is_directory(self) -> None:
        name = 'missing'
        path = self.notification_directory / name
        path.mkdir(parents=True)
        file = phile.notify.File(path=path)
        self.assertTrue(not file.load())

    def test_save_sets_file_content_and_modified_time(self) -> None:
        text = 'Reminder.'
        path = self.notification_directory / 'b'
        file = phile.notify.File(path=path, text=text)
        before = round_down_to_two_seconds(datetime.datetime.now())
        file.save()
        after = round_up_to_two_seconds(datetime.datetime.now())
        self.assertEqual(path.read_text(), text)
        self.assertLessEqual(file.modified_at, after)
        self.assertGreaterEqual(file.modified_at, before)


if __name__ == '__main__':
    unittest.main()
