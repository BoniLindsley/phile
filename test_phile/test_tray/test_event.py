#!/usr/bin/env python3
"""
---------------------
Test phile.tray.event
---------------------
"""

# Standard library.
import logging
import pathlib
import tempfile
import unittest
import unittest.mock

# External dependencies.
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray
import phile.tray.event


class TestHandler(unittest.TestCase):
    """Tests :data:`~phile.tray.event.Handler`."""

    def test_lambda(self) -> None:
        """A lambda can be a :data:`~phile.tray.event.Handler`."""
        _: phile.tray.event.Handler = lambda _: None

    def test_function(self) -> None:
        """A function can be a :data:`~phile.tray.event.Handler`."""

        def tray_handle_function(tray_file: phile.tray.File) -> None:
            pass

        _: phile.tray.event.Handler = tray_handle_function


class TestFilter(unittest.TestCase):
    """Tests :class:`~phile.tray.event.Filter`."""

    def setUp(self) -> None:
        """
        Create a directory for storing tray files.

        The directory is not actually used,
        in terms of saving files in it,
        but a path is necessary to be used as a tray file directory.
        Not using default directory, in case it can cause conflicts.
        """
        tray_directory = tempfile.TemporaryDirectory()
        self.addCleanup(tray_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            tray_directory=pathlib.Path(tray_directory.name),
            tray_suffix='.trailer',
        )
        self.event_handler = unittest.mock.Mock()
        self.filter = phile.tray.event.Filter(
            configuration=self.configuration,
            event_handler=self.event_handler,
        )

    def test_initialisation_with_parameters(self) -> None:
        """
        Initialising a :class:`~phile.tray.event.Filter`
        with named parameters works.
        """

    def test_forward_tray_file_events_to_event_handler(self) -> None:
        """Events that are tray file events should be forwarded."""
        event = watchdog.events.FileCreatedEvent(
            str(
                self.configuration.tray_directory /
                ('good' + self.configuration.tray_suffix)
            )
        )
        self.filter(event)
        self.event_handler.assert_called_with(event)
        self.assertEqual(self.event_handler.call_count, 1)

    def test_ignores_directory_events(self) -> None:
        """Directory events are not tray file events."""
        event = watchdog.events.DirCreatedEvent(
            str(
                self.configuration.tray_directory /
                ('primer' + self.configuration.tray_suffix)
            )
        )
        self.filter(event)
        self.event_handler.assert_not_called()

    def test_ignores_wrong_suffix(self) -> None:
        """File events of the wrong suffix are not tray file events."""
        event = watchdog.events.FileCreatedEvent(
            str(
                self.configuration.tray_directory /
                ('primer' + self.configuration.tray_suffix + '_no')
            )
        )
        self.filter(event)
        self.event_handler.assert_not_called()

    def test_ignores_wrong_directory(self) -> None:
        """File events in a wrong directory are not tray file events."""
        event = watchdog.events.FileCreatedEvent(
            str(
                self.configuration.tray_directory / 'subdirectory' /
                ('primer' + self.configuration.tray_suffix)
            )
        )
        self.filter(event)
        self.event_handler.assert_not_called()

    def test_splitting_move_events(self) -> None:
        """Move events should be split into delete and create events."""
        source_path = self.configuration.tray_directory / (
            'source' + self.configuration.tray_suffix
        )
        dest_path = self.configuration.tray_directory / (
            'dest' + self.configuration.tray_suffix
        )
        event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.filter(event)
        self.event_handler.assert_has_calls(
            [
                unittest.mock.call(
                    watchdog.events.FileDeletedEvent(str(source_path))
                ),
                unittest.mock.call(
                    watchdog.events.FileCreatedEvent(str(dest_path))
                )
            ],
            any_order=True,
        )
        self.assertEqual(self.event_handler.call_count, 2)

    def test_splitting_move_events_can_ignore_source(self) -> None:
        """Move events with non-tray-file source ignores source."""
        source_path = self.configuration.tray_directory / (
            'source' + self.configuration.tray_suffix + '_no'
        )
        dest_path = self.configuration.tray_directory / (
            'dest' + self.configuration.tray_suffix
        )
        event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.filter(event)
        self.event_handler.assert_called_with(
            watchdog.events.FileCreatedEvent(str(dest_path))
        )
        self.assertEqual(self.event_handler.call_count, 1)

    def test_splitting_move_events_can_ignore_dest(self) -> None:
        """Move events with non-tray-file dest ignores dest."""
        source_path = self.configuration.tray_directory / (
            'source' + self.configuration.tray_suffix
        )
        dest_path = self.configuration.tray_directory / (
            'dest' + self.configuration.tray_suffix + '_no'
        )
        event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        self.filter(event)
        self.event_handler.assert_called_with(
            watchdog.events.FileDeletedEvent(str(source_path))
        )
        self.assertEqual(self.event_handler.call_count, 1)


class TestConverter(unittest.TestCase):
    """Tests :class:`~phile.tray.event.Converter`."""

    def setUp(self) -> None:
        """
        Create a directory for storing tray files.

        The directory is not actually used,
        in terms of saving files in it,
        but a path is necessary to be used as a tray file directory.
        Not using default directory, in case it can cause conflicts.
        """
        tray_directory = tempfile.TemporaryDirectory()
        self.addCleanup(tray_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            tray_directory=pathlib.Path(tray_directory.name),
            tray_suffix='.trailer',
        )
        self.tray_handler = unittest.mock.Mock()
        self.converter = phile.tray.event.Converter(
            configuration=self.configuration,
            tray_handler=self.tray_handler,
        )

    def test_initialisation_with_parameters(self) -> None:
        """
        Initialising a :class:`~phile.tray.event.Converter`
        with named parameters works.
        """

    def test_forward_tray_file_events_to_tray_handler(self) -> None:
        """Events that are tray file events should be forwarded."""
        tray_path = self.configuration.tray_directory / (
            'good' + self.configuration.tray_suffix
        )
        event = watchdog.events.FileCreatedEvent(str(tray_path))
        self.converter(event)
        self.tray_handler.assert_called_with(
            phile.tray.File(path=tray_path)
        )
        self.assertEqual(self.tray_handler.call_count, 1)

    def test_asserts_on_move_events(self) -> None:
        """Move events must be split before given to converter."""
        source_path = self.configuration.tray_directory / (
            'source' + self.configuration.tray_suffix
        )
        dest_path = self.configuration.tray_directory / (
            'dest' + self.configuration.tray_suffix
        )
        event = watchdog.events.FileMovedEvent(
            str(source_path), str(dest_path)
        )
        with self.assertRaises(AssertionError):
            self.converter(event)


class TestSorterHandler(unittest.TestCase):
    """Tests :data:`~phile.tray.event.Sorter.Handler`."""

    def test_lambda(self) -> None:
        """A lambda can be a :data:`~phile.tray.event.Sorter.Handler`."""
        _: phile.tray.event.Sorter.Handler = (
            lambda index, tray_file: None
        )

    def test_function(self) -> None:
        """
        A function can be a :data:`~phile.tray.event.Sorter.Handler`.
        """

        def sorter_handle_function(
            index: int, tray_file: phile.tray.File
        ) -> None:
            pass

        _: phile.tray.event.Sorter.Handler = sorter_handle_function


class TestSorter(unittest.TestCase):
    """Tests :class:`~phile.tray.event.Sorter`."""

    def setUp(self) -> None:
        """Create a directory for storing tray files."""
        tray_directory = tempfile.TemporaryDirectory()
        self.addCleanup(tray_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            tray_directory=pathlib.Path(tray_directory.name),
            tray_suffix='.trailer',
        )
        self.insert = unittest.mock.Mock()
        self.pop = unittest.mock.Mock()
        self.set_item = unittest.mock.Mock()
        self.sorter = phile.tray.event.Sorter(
            configuration=self.configuration,
            insert=self.insert,
            pop=self.pop,
            set_item=self.set_item
        )

    def test_initialisation_with_parameters(self) -> None:
        """
        Initialising a :class:`~phile.tray.event.Sorter`
        with named parameters works.
        """
        self.assertListEqual(self.sorter.tray_files, [])

    def test_is_event_handler(self) -> None:
        """An instance is a :data:`~phile.tray.event.Handler`."""

    def test_insert_new_untracked_tray_files_from_empty(self) -> None:
        """Tray files that exist but untracked are given to insert."""
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='first'
        )
        tray_file.save()
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [tray_file])
        self.assertListEqual(
            self.insert.call_args_list,
            [unittest.mock.call(0, tray_file)]
        )
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_insert_new_untracked_tray_files_from_non_empty(
        self
    ) -> None:
        """Insert new untrack tray file when list non-empty."""
        # Fill in the list with something first.
        prev_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='zero'
        )
        prev_tray_file.save()
        self.sorter(prev_tray_file)
        self.assertListEqual(self.sorter.tray_files, [prev_tray_file])
        self.insert.reset_mock()
        # And then test insert.
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='first'
        )
        tray_file.save()
        self.sorter(tray_file)
        self.assertListEqual(
            self.sorter.tray_files, [tray_file, prev_tray_file]
        )
        call_mock = unittest.mock.Mock()
        call_mock(0, tray_file)
        self.assertListEqual(
            self.insert.call_args_list,
            [unittest.mock.call(0, tray_file)]
        )
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_set_modified_tracked_tray_files(self) -> None:
        """Tray files that exist and tracked are given to set_item."""
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='first'
        )
        tray_file.save()
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [tray_file])
        self.assertListEqual(
            self.insert.call_args_list,
            [unittest.mock.call(0, tray_file)]
        )
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_pop_missing_tracked_tray_files(self) -> None:
        """Tray files that do not exist and tracked are popped."""
        # Fill in the list with something first.
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='zero'
        )
        tray_file.save()
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [tray_file])
        self.insert.reset_mock()
        # And then test pop.
        tray_file.path.unlink()
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [])
        self.insert.assert_not_called()
        self.assertListEqual(
            self.pop.call_args_list, [unittest.mock.call(0, tray_file)]
        )
        self.set_item.assert_not_called()

    def test_ignore_untracked_non_existent_tray_files(self) -> None:
        """Tray files that do not exist and untracted are ignored."""
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='not_exists'
        )
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [])
        self.insert.assert_not_called()
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_ignore_bad_file(self) -> None:
        """
        Ignores badly structured files.

        There is not much we can do about it as a reader.
        """
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='bad'
        )
        tray_file.icon_name = 'phile-tray-empty'
        tray_file.save()
        with tray_file.path.open('a+') as file_stream:
            file_stream.write('Extra text.')
        with self.assertLogs(
            logger='phile.tray.event', level=logging.WARNING
        ) as logs:
            self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [])
        self.insert.assert_not_called()
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_load_all(self) -> None:
        """Load all adds all tray files to list."""
        tray_file_first = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='first'
        )
        tray_file_second = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='second'
        )
        tray_file_first.save()
        tray_file_second.save()
        self.sorter.load_all()
        self.assertListEqual(
            self.sorter.tray_files, [tray_file_first, tray_file_second]
        )
        self.assertSetEqual({
            call_args[0][1].path
            for call_args in self.insert.call_args_list
        }, {tray_file_first.path, tray_file_second.path})
        self.pop.assert_not_called()
        self.set_item.assert_not_called()

    def test_load_all_asserts_if_not_empty(self) -> None:
        """Load all asserts on the tracked list being empty."""
        # Fill in the list with something first.
        tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='something'
        )
        tray_file.save()
        self.sorter(tray_file)
        self.assertListEqual(self.sorter.tray_files, [tray_file])
        # Now that the list is not empty, we expect an assertion.
        with self.assertRaises(AssertionError):
            self.sorter.load_all()


if __name__ == '__main__':
    unittest.main()
