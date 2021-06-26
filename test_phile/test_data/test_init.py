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
import phile.configuration
import phile.data
from test_phile.test_configuration.test_init import UsesConfiguration


class BasicLoadData(phile.data.SortableLoadData):
    path: pathlib.Path = pathlib.Path('a')


class TestSortableLoadData(unittest.TestCase):

    def test_subclass_can_inherit_methods_to_satisfy_protocol(
        self
    ) -> None:
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
        configuration: phile.configuration.Entries,
        **kwargs: typing.Any,
    ) -> pathlib.Path:
        del configuration
        return pathlib.Path(path_stem + cls.suffix)


class TestFileMakePath(UsesConfiguration, unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.data_suffix = '.phile'
        self.path_filter = functools.partial(
            phile.data.File.check_path, configuration=self.configuration
        )

    def test_make_path__from_stem_and_configuration(self) -> None:
        stem = 'name'
        expected_path = self.state_directory_path / (
            stem + self.data_suffix
        )
        file_path = phile.data.File.make_path(
            stem, configuration=self.configuration
        )
        self.assertEqual(file_path, expected_path)

    def test_from_path_stem__and_configuration(self) -> None:
        stem = 'name'
        path = self.state_directory_path / (stem + self.data_suffix)
        file = phile.data.File.from_path_stem(
            stem, configuration=self.configuration
        )
        self.assertEqual(file.path, path)

    def test_subclass_by_implementing_make_path(self) -> None:
        stem = 'name'
        path = pathlib.Path(stem + SubFile.suffix)
        file = SubFile.from_path_stem(
            stem, configuration=self.configuration
        )
        self.assertEqual(file.path, path)

    def test_check_path__that_passes(self) -> None:
        name = 'name' + self.data_suffix
        path = self.state_directory_path / name
        self.assertTrue(
            phile.data.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_check_path__of_subclass(self) -> None:
        self.assertTrue(
            SubFile.check_path(
                configuration=self.configuration,
                path=pathlib.Path('a.home')
            )
        )

    def test_check_path__is_a_filter_that_uses_configuration(
        self
    ) -> None:
        name = 'name' + self.data_suffix
        path = self.state_directory_path / name
        self.assertTrue(self.path_filter(path))

    def test_make_path__return_value_passes_check_path(self) -> None:
        path_stem = 'stem'
        path = phile.data.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_check_path__fails_if_wrong_directory(self) -> None:
        name = 'name' + self.data_suffix
        path = self.state_directory_path / name / name
        self.assertTrue(not self.path_filter(path))

    def test_check_path__fails_if_wrong_suffix(self) -> None:
        name = 'name' + self.data_suffix + '_not'
        path = self.state_directory_path / name
        self.assertTrue(not self.path_filter(path))


class TestFile(unittest.TestCase):

    def test_init__with_keywords(self) -> None:
        file = phile.data.File(path=pathlib.Path())
        self.assertTrue(hasattr(file, 'path'))
        phile.data.File(path=pathlib.Path('a'))

    def test_satisfies_sortable_load_data_protocol(self) -> None:
        _: phile.data.SortableLoadData = phile.data.File(
            path=pathlib.Path()
        )

    def test_implements_less_than_partial_order(self) -> None:
        self.assertEqual(
            phile.data.File(path=pathlib.Path()),
            phile.data.File(path=pathlib.Path())
        )
        self.assertLess(
            phile.data.File(path=pathlib.Path('a')),
            phile.data.File(path=pathlib.Path('b'))
        )

    def test_partial_order_with_path(self) -> None:
        self.assertEqual(
            phile.data.File(path=pathlib.Path()), pathlib.Path()
        )
        self.assertLess(
            phile.data.File(path=pathlib.Path('a')), pathlib.Path('b')
        )

    def test_does_not_compare_with_arbitrary_objects(self) -> None:
        self.assertNotEqual(phile.data.File(path=pathlib.Path()), 0)
        with self.assertRaises(TypeError):
            self.assertLess(phile.data.File(path=pathlib.Path('a')), 'b')


class TestUpdateCallback(unittest.TestCase):

    def test_subclass_can_inherit_methods_to_satisfy_protocol(
        self
    ) -> None:

        class BasicUpdateCallback(
            phile.data.UpdateCallback[BasicLoadData]
        ):
            pass

        data = BasicLoadData()
        BasicUpdateCallback()(0, data, [data])


class TestCreateFile(unittest.TestCase):

    def test_subclass_can_inherit_methods_to_satisfy_protocol(
        self
    ) -> None:

        class BasicCreateFile(phile.data.CreateFile[BasicLoadData]):
            pass

        create_file = BasicCreateFile()
        create_file(pathlib.Path())


class TestSortedLoadCache(unittest.TestCase):

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

    def test_callbacks_can_be_any_callables(self) -> None:

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

    def test_update_with_loaded_untracked_data_inserts_it(self) -> None:
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

    def test_update_with_unloaded_untracked_data_does_nothing(
        self
    ) -> None:
        source_path = self.data_directory_path / 'mising'
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_with_loaded_tracked_data_resets_it(self) -> None:
        self.test_update_with_loaded_untracked_data_inserts_it()
        source_path = self.cache.tracked_data[0].path
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 1)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )

    def test_update_with_unloaded_tracked_data_pops_it(self) -> None:
        self.test_update_with_loaded_untracked_data_inserts_it()
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
        # It previously overridden position zero instead of prepending.
        self.test_update_with_loaded_untracked_data_inserts_it()
        source_path = self.data_directory_path / 'before'
        source_path.touch()
        self.cache.update(source_path)
        self.assertEqual(len(self.cache.tracked_data), 2)
        self.on_insert.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_paths_can_insert_and_set(self) -> None:
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

    def test_update_no_paths_does_nothing(self) -> None:
        self.cache.update_paths([])
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_tracked_without_tracked_does_nothing(self) -> None:
        self.cache.update_tracked()
        self.assertEqual(len(self.cache.tracked_data), 0)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_not_called()

    def test_update_tracked_stays_loaded_sets_data(self) -> None:
        self.test_update_with_loaded_untracked_data_inserts_it()
        source_path = self.cache.tracked_data[0].path
        self.cache.update_tracked()
        self.assertEqual(len(self.cache.tracked_data), 1)
        self.on_insert.assert_not_called()
        self.on_pop.assert_not_called()
        self.on_set.assert_called_once_with(
            0, phile.data.File(path=source_path), self.cache.tracked_data
        )

    def test_refresh_can_unload(self) -> None:
        self.test_update_with_loaded_untracked_data_inserts_it()
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
