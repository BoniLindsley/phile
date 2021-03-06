#!/usr/bin/env python3
"""
----------------------
Test :mod:`phile.data`
----------------------
"""

# Standard library.
import functools
import pathlib
import tempfile
import typing
import unittest
import unittest.mock

# Internal packages.
import phile
import phile.data


class BasicLoadData(phile.data.SortableLoadData):
    path: pathlib.Path = pathlib.Path('a')


class TestSortableLoadData(unittest.TestCase):
    """Tests :data:`~phile.data.SortableLoadData`."""

    def test_subclass(self) -> None:
        """Subclass of protocol can inherit methods to satisfy it."""

        data = BasicLoadData()
        data == data
        data < data
        data.load()


class SubFile(phile.data.File):

    suffix = '.home'

    @classmethod
    def make_path(
        cls,
        path_stem: str,
        *args: typing.Any,
        configuration: phile.Configuration,
        **kwargs: typing.Any,
    ) -> pathlib.Path:
        del configuration
        return pathlib.Path(path_stem + cls.suffix)


class TestFileMakePath(unittest.TestCase):
    """Tests :meth:`~phile.data.File.make_path`."""

    def set_up_configuration(self) -> None:
        data_directory = tempfile.TemporaryDirectory()
        self.addCleanup(data_directory.cleanup)
        self.configuration = configuration = (
            phile.Configuration(
                user_state_directory=pathlib.Path(data_directory.name)
            )
        )
        self.data_directory = configuration.user_state_directory
        self.data_suffix = '.phile'

    def set_up_path_filter(self) -> None:
        self.path_filter = path_filter = functools.partial(
            phile.data.File.check_path, configuration=self.configuration
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_path_filter()

    def test_make_path(self) -> None:
        """Call make_path."""
        stem = 'name'
        expected_path = self.data_directory / (stem + self.data_suffix)
        file_path = phile.data.File.make_path(
            stem, configuration=self.configuration
        )
        self.assertEqual(file_path, expected_path)

    def test_from_path_stem(self) -> None:
        """Constructing with just path stem should be possible."""
        stem = 'name'
        path = self.data_directory / (stem + self.data_suffix)
        file = phile.data.File.from_path_stem(
            stem, configuration=self.configuration
        )
        self.assertEqual(file.path, path)

    def test_subclass_from_path_stem(self) -> None:
        """Subclasses can create by implementing ``make_path``."""
        stem = 'name'
        path = pathlib.Path(stem + SubFile.suffix)
        file = SubFile.from_path_stem(
            stem, configuration=self.configuration
        )
        self.assertEqual(file.path, path)

    def test_match(self) -> None:
        """Check an explicit path that should pass."""
        name = 'name' + self.data_suffix
        path = self.data_directory / name
        self.assertTrue(
            phile.data.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_subclass_match(self) -> None:
        """Subclasses can match by implementing ``make_path``."""
        self.assertTrue(
            SubFile.check_path(
                configuration=self.configuration,
                path=pathlib.Path('a.home')
            )
        )

    def test_partial_for_filter(self) -> None:
        """
        Usable as a single parameter callback
        using :func:`~functools.partial`.
        """
        name = 'name' + self.data_suffix
        path = self.data_directory / name
        self.assertTrue(self.path_filter(path))

    def test_make_path_result(self) -> None:
        """Result of :meth:`~phile.data.File.make_path` should pass."""
        path_stem = 'stem'
        path = phile.data.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_directory_mismatch(self) -> None:
        name = 'name' + self.data_suffix
        path = self.data_directory / name / name
        self.assertTrue(not self.path_filter(path))

    def test_suffix_mismatch(self) -> None:
        name = 'name' + self.data_suffix + '_not'
        path = self.data_directory / name
        self.assertTrue(not self.path_filter(path))


class TestFile(unittest.TestCase):
    """Tests :data:`~phile.data.File`."""

    def test_init(self) -> None:
        """Test keyword initialisation."""
        file = phile.data.File(path=pathlib.Path())
        self.assertTrue(hasattr(file, 'path'))
        phile.data.File(path=pathlib.Path('a'))

    def test_is_sortable_load_data(self) -> None:
        """Satisfies :class:`~phile.data.SortableLoadData` protocol."""
        _: phile.data.SortableLoadData = phile.data.File(
            path=pathlib.Path()
        )

    def test_compare(self) -> None:
        """Implements less-than partial order."""
        self.assertEqual(
            phile.data.File(path=pathlib.Path()),
            phile.data.File(path=pathlib.Path())
        )
        self.assertLess(
            phile.data.File(path=pathlib.Path('a')),
            phile.data.File(path=pathlib.Path('b'))
        )

    def test_compare_with_path(self) -> None:
        """Implements partial order with :class:~pathlib.Path`."""
        self.assertEqual(
            phile.data.File(path=pathlib.Path()), pathlib.Path()
        )
        self.assertLess(
            phile.data.File(path=pathlib.Path('a')), pathlib.Path('b')
        )

    def test_compare_with_object(self) -> None:
        """Does not implement comparison with arbitrary objects."""
        self.assertNotEqual(phile.data.File(path=pathlib.Path()), 0)
        with self.assertRaises(TypeError):
            self.assertLess(phile.data.File(path=pathlib.Path('a')), 'b')


class TestUpdateCallback(unittest.TestCase):
    """Tests :class:`~phile.data.UpdateCallback`."""

    def test_subclass(self) -> None:
        """Subclass of protocol can inherit methods to satisfy it."""

        class BasicUpdateCallback(
            phile.data.UpdateCallback[BasicLoadData]
        ):
            pass

        data = BasicLoadData()
        BasicUpdateCallback()(0, data, [data])


class TestCreateFile(unittest.TestCase):
    """Tests :class:`~phile.data.CreateFile`."""

    def test_subclass(self) -> None:
        """Subclass of protocol can inherit methods to satisfy it."""

        class BasicCreateFile(phile.data.CreateFile[BasicLoadData]):
            pass

        create_file = BasicCreateFile()
        create_file(pathlib.Path())


class TestSortedLoadCache(unittest.TestCase):
    """Tests :class:`~phile.data.SortedLoadCache`."""

    def setUp(self) -> None:
        """Create cache object with mock callbacks."""
        data_directory = tempfile.TemporaryDirectory()
        self.addCleanup(data_directory.cleanup)
        self.data_directory_path = pathlib.Path(data_directory.name)
        self.on_insert = unittest.mock.Mock()
        self.on_pop = unittest.mock.Mock()
        self.on_set = unittest.mock.Mock()
        self.cache = phile.data.SortedLoadCache[phile.data.File](
            create_file=phile.data.File,
            on_insert=self.on_insert,
            on_pop=self.on_pop,
            on_set=self.on_set,
        )

    def test_init_callbacks(self) -> None:
        """Callbacks can be given as functions, lambdas and callables."""

        class update_callback:

            def __call__(
                self, index: int, changed_data: phile.data.File,
                tracked_data: typing.List[phile.data.File]
            ) -> None:
                pass

        def update_function(
            index: int, changed_data: phile.data.File,
            tracked_data: typing.List[phile.data.File]
        ) -> None:
            pass

        data = phile.data.File(path=pathlib.Path())
        cache = phile.data.SortedLoadCache[phile.data.File](
            create_file=lambda source_path: data,
            on_insert=lambda _1, _2, _3: None,
            on_pop=update_function,
            on_set=update_callback(),
        )
        self.assertEqual(cache.create_file(pathlib.Path()), data)

    def test_update_with_loaded_untracked_data(self) -> None:
        """
        Successful :meth:`~phile.data.SortedLoadCache.update`
        with untracked data inserts it.
        """
        source_path = self.data_directory_path / 'exists'
        source_path.touch()
        self.cache.update(source_path)
        self.assertListEqual(
            self.cache.tracked_data, [phile.data.File(path=source_path)]
        )
        self.on_insert.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()
        self.on_insert.reset_mock()

    def test_update_with_unloaded_untracked_data(self) -> None:
        """
        Unsuccessful :meth:`~phile.data.SortedLoadCache.update`
        with untracked data does nothing.
        """
        source_path = self.data_directory_path / 'mising'
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_with_loaded_tracked_data(self) -> None:
        """
        Successful re-:meth:`~phile.data.SortedLoadCache.update`
        with tracked data re-sets it.
        """
        self.test_update_with_loaded_untracked_data()
        source_path = self.cache.tracked_data[0].path
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 1)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )

    def test_update_with_unloaded_tracked_data(self) -> None:
        """
        Unsuccessful :meth:`~phile.data.SortedLoadCache.update`
        with tracked data pops it.
        """
        self.test_update_with_loaded_untracked_data()
        source_path = self.cache.tracked_data[0].path
        source_path.unlink()
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )
        self.on_set.assert_not_called()

    def test_prepend_to_non_empty_tracked_list(self) -> None:
        """
        It previously overridden position zero instead of prepending.
        """
        self.test_update_with_loaded_untracked_data()
        source_path = self.data_directory_path / 'before'
        source_path.touch()
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 2)
        self.on_insert.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_paths(self) -> None:
        """
        :meth:`~phile.data.SortedLoadCache.update_paths`
        can :meth:`~phile.data.SortedLoadCache.on_insert`
        and :meth:`~phile.data.SortedLoadCache.on_set`.
        """
        source_path = self.data_directory_path / 'exists'
        source_path.touch()
        self.cache.update_paths([source_path, source_path])
        self.assertEqual(len(self.cache.tracked_data), 1)
        self.on_insert.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )
        self.on_pop.assert_not_called()
        self.on_set.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )

    def test_update_no_paths(self) -> None:
        """
        :meth:`~phile.data.SortedLoadCache.update_paths`
        with no paths does nothing.
        """
        self.cache.update_paths([])
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_tracked_without_tracked(self) -> None:
        """
        :meth:`~phile.data.SortedLoadCache.update_tracked` does nothing
        if :data:`~phile.data.SortedLoadCache.tracked_data` is empty.
        """
        self.cache.update_tracked()
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_tracked_stays_loaded(self) -> None:
        """
        Successful :meth:`~phile.data.SortedLoadCache.update_tracked`
        sets data.
        """
        self.test_update_with_loaded_untracked_data()
        source_path = self.cache.tracked_data[0].path
        self.cache.update_tracked()
        self.assertEqual(len(self.cache.tracked_data), 1)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )

    def test_refresh_can_unload(self) -> None:
        """
        Directory :meth:`~phile.data.SortedLoadCache.refresh`
        does an :meth:`~phile.data.SortedLoadCache.update`
        """
        self.test_update_with_loaded_untracked_data()
        source_path = self.cache.tracked_data[0].path
        source_path.unlink()
        new_source_path = self.data_directory_path / 'two'
        new_source_path.touch()
        self.cache.refresh(
            data_directory=self.data_directory_path, data_file_suffix=''
        )
        self.assertListEqual(
            self.cache.tracked_data,
            [phile.data.File(path=new_source_path)]
        )


if __name__ == '__main__':
    unittest.main()
