#!/usr/bin/env python3
"""
----------------------
Test phile.trigger GUI
----------------------
"""

# Standard library.
import datetime
import logging
import pathlib
import pkg_resources
import tempfile
import unittest
import unittest.mock

# External dependencies.
from PySide2.QtCore import QEventLoop, QObject, Qt
from PySide2.QtGui import QIcon

# Internal packages.
from phile.configuration import Configuration
from phile.tray.gui import GuiIconList, set_icon_paths, TrayFile
from test_phile.pyside2_test_tools import (
    QTestApplication, q_icon_from_theme, SystemTrayIcon
)
from test_phile.threaded_mock import ThreadedMock

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestTrayFile(unittest.TestCase):
    """
    Unit test for :class:`~phile.notify.tray.TrayFile`.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a directory to use as a tray directory.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        self.tray_directory = tempfile.TemporaryDirectory()
        self.tray_directory_path = pathlib.Path(self.tray_directory.name)
        self.configuration = Configuration(
            tray_directory=self.tray_directory_path
        )
        self.name = 'clock'
        self.path = self.configuration.tray_directory / (
            self.name + self.configuration.tray_suffix
        )
        self.tray = TrayFile(
            name=self.name, configuration=self.configuration
        )

    def tearDown(self) -> None:
        """Remove tray directory."""
        self.tray_directory.cleanup()

    def test_construct_with_name(self) -> None:
        """Constructing with name must come with a configuration."""
        # A successful construction in `setUp()`.
        self.assertEqual(self.tray.name, self.name)
        self.assertEqual(self.tray.path, self.path)
        # It should fail without a configuration give.
        with self.assertRaises(ValueError):
            TrayFile(name=self.name)

    def test_construct_with_path(self) -> None:
        """Constructing with just path should be possible."""
        tray = TrayFile(
            path=self.configuration.tray_directory /
            (self.name + self.configuration.tray_suffix)
        )
        self.assertEqual(self.tray.path, self.path)

    def test_construct_with_path_with_wrong_parent(self) -> None:
        """Constructing with path must be in configured directory."""
        with self.assertRaises(TrayFile.ParentError):
            tray = TrayFile(
                configuration=self.configuration,
                path=self.configuration.tray_directory / 'subdir' /
                (self.name + self.configuration.tray_suffix)
            )

    def test_construct_with_path_with_wrong_suffix(self) -> None:
        """Constructing with path must be in configured suffix."""
        with self.assertRaises(TrayFile.SuffixError):
            tray = TrayFile(
                configuration=self.configuration,
                path=self.configuration.tray_directory /
                (self.name + '.wrong_suffix')
            )

    def test_hash(self) -> None:
        """Can be used as keys in dictionaries."""
        number = 1
        tray_key_dictionary = {self.tray: number}
        self.assertEqual(tray_key_dictionary[self.tray], number)

    def test_lt(self) -> None:
        """Can be used as keys in dictionaries."""
        smaller_tray = TrayFile(
            name='smaller.tray', configuration=self.configuration
        )
        self.assertLess(self.tray, smaller_tray)

    def test_remove_file(self) -> None:
        """Tray can be removed."""
        self.tray.path.touch()
        self.assertTrue(self.tray.path.is_file())
        self.tray.remove()
        self.assertTrue(not self.tray.path.is_file())

    def test_remove_non_existent_file(self) -> None:
        """Removing trays that do not exist should be fine."""
        self.assertTrue(not self.tray.path.is_file())
        self.tray.remove()
        self.assertTrue(not self.tray.path.is_file())

    def test_load(self) -> None:
        """Parse a tray file for information."""
        data = {
            'icon_name': 'phile-tray',
            'icon_path': self.tray_directory_path / 'phile-tray-read',
            'text_icon': 'N',
        }
        content = '{text_icon}\n{{'
        content += '"icon_name": "{icon_name}"'
        content += ',"icon_path": "{icon_path}"'
        content += '}}'
        content = content.format(**data)
        self.tray.path.write_text(content)
        self.tray.load()
        self.assertEqual(self.tray.icon_name, data['icon_name'])
        self.assertEqual(self.tray.icon_path, data['icon_path'])
        self.assertEqual(self.tray.text_icon, data['text_icon'])

    def test_save(self) -> None:
        """Save a tray file with some information."""
        data = {
            'icon_name': 'phile-tray',
            'text_icon': 'N',
        }
        expected_content = '{text_icon}\n{{'
        expected_content += '"icon_name": "{icon_name}"'
        expected_content += '}}'
        expected_content = expected_content.format(**data)
        self.tray.icon_name = data['icon_name']
        self.tray.text_icon = data['text_icon']
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertEqual(content, expected_content)

    def test_save_nothing(self) -> None:
        """Savea blank tray file. It should still have a new line."""
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertTrue(not content)


class TestSetIconPaths(unittest.TestCase):
    """Unit test for :class:`~phile.tray.set_icon_paths`."""

    def __init__(self, *args, **kwargs) -> None:
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        self.app = QTestApplication()

    def tearDown(self) -> None:
        """
        Shutdown PySide2 application after each method test.

        PySide2 Applications act as singletons.
        Any previous instances must be shutdown
        before a new one can be created.
        """
        self.app.tear_down()

    def test_call(self) -> None:
        """Just call it."""
        set_icon_paths()
        resource_dir_path = pathlib.Path(
            pkg_resources.resource_filename('phile.tray', "resources")
        )
        self.assertIn(
            str(resource_dir_path / 'icons'), QIcon.themeSearchPaths()
        )
        self.assertIn(
            str(resource_dir_path / 'pixmaps'),
            QIcon.fallbackSearchPaths()
        )
        self.assertEqual(QIcon.fallbackThemeName(), 'blank')


class TestGuiIconList(unittest.TestCase):
    """
    Unit test for :class:`~phile.tray.gui.GuiIconList`.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        self.tray_directory = tempfile.TemporaryDirectory()
        self.tray_directory_path = pathlib.Path(self.tray_directory.name)
        self.configuration = Configuration(
            tray_directory=self.tray_directory_path
        )
        self.app = QTestApplication()
        self.gui_icon_list = GuiIconList(
            configuration=self.configuration
        )

    def tearDown(self) -> None:
        """
        Shutdown PySide2 application after each method test.

        PySide2 Applications act as singletons.
        Any previous instances must be shutdown
        before a new one can be created.
        """
        self.gui_icon_list.deleteLater()
        self.app.tear_down()
        self.tray_directory.cleanup()

    def test_initialisation(self) -> None:
        """Create a MainWindow object."""
        # The object is created in `setUp`.
        # This tests flags up whether the constructor itself fails.
        gui_icon_list = self.gui_icon_list
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        # Test also that the icon list can be created without arguments.
        GuiIconList().deleteLater()

    def test_initialisation_with_custom_monitor(self) -> None:
        """
        Create a :class:`phile.tray.gui.GuiIconList` object with a
        :class:`phile.PySide2_extras.watchdog_wrapper.FileSystemMonitor`.
        """
        # Create another instance of `GuiIconList`
        # and ignore the one created in `setUp`.
        # Use the monitor from it though,
        # so we don't have to create another one.
        file_system_monitor = self.gui_icon_list._file_system_monitor
        gui_icon_list = GuiIconList(
            configuration=self.configuration,
            file_system_monitor=file_system_monitor
        )
        # Test for the same properties.
        self.assertEqual(
            gui_icon_list._file_system_monitor, file_system_monitor
        )
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list._signal_emitter.is_started())
        self.assertTrue(not file_system_monitor.was_start_called())
        self.assertTrue(not file_system_monitor.was_stop_called())
        # Clean-up.
        gui_icon_list.deleteLater()
        self.app.process_deferred_delete_events()

    def test_show_and_hide_without_tray_icones(self) -> None:
        """Showing and hiding should start and stop file monitoring."""
        # Showing should start monitoring.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        # Hiding should stop monitoring.
        # This should be done by stopping the emitter
        # and not the file system monitor
        # so that the monitor can be started up again if necessary.
        gui_icon_list.hide()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        # Try to show again to ensure toggling works.
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )

    def test_hide_without_show(self) -> None:
        """Calling hide without showing should just not do anything."""
        gui_icon_list = self.gui_icon_list
        gui_icon_list.hide()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_show_and_hide(self) -> None:
        """Showing and hiding should apply to its tray icons."""
        # Create a tray.
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        tray.save()
        # Need icon paths to test icon loading.
        set_icon_paths()
        # Showing should start monitoring.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertTrue(gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertTrue(children[0].isVisible())
        # Hiding should stop monitoring.
        # This should be done by stopping the emitter
        # and not the file system monitor
        # so that the monitor can be started up again if necessary.
        gui_icon_list.hide()
        self.assertTrue(not gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertTrue(not children[0].isVisible())

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    def test_load_icon_from_name(self) -> None:
        """Retrive icon based on a icon name in tray file data."""
        # Create a tray.
        _logger.debug('Creating tray file.')
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        resource_dir_path = pathlib.Path(
            pkg_resources.resource_filename('phile.tray', "resources")
        )
        tray.icon_name = 'phile-tray-empty'
        _logger.debug('Setting icon paths.')
        set_icon_paths()
        _logger.debug('Loading tray icon.')
        gui_icon_list = self.gui_icon_list
        new_icon = gui_icon_list.load_icon(tray)
        self.assertTrue(not new_icon.isNull())
        self.assertEqual(new_icon.name(), tray.icon_name)
        _logger.debug('End of test.')

    def test_load_icon_from_path(self) -> None:
        """Retrive icon based on a icon path in tray file data."""
        # Create a tray.
        _logger.debug('Creating tray file.')
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        resource_dir_path = pathlib.Path(
            pkg_resources.resource_filename('phile.tray', "resources")
        )
        tray.icon_path = (
            resource_dir_path / 'icons' / 'blank' / '64x64' / 'status' /
            'phile-tray-empty.png'
        )
        # Try to get an icon.
        gui_icon_list = self.gui_icon_list
        _logger.debug('Loading tray icon.')
        new_icon = gui_icon_list.load_icon(tray)
        self.assertTrue(not new_icon.isNull())
        _logger.debug('End of test.')

    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_show_with_bad_file(self) -> None:
        """
        Show ignores badly structured files.

        There is not much we can do about it as a reader.
        """
        # Create a tray.
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        tray.icon_name = 'phile-tray-empty'
        tray.text_icon = 'A'
        tray.save()
        with tray.path.open('a+') as file_stream:
            file_stream.write('Extra text.')
        # Check that they are all detected when showing the tray icons.
        gui_icon_list = self.gui_icon_list
        with self.assertWarns(UserWarning):
            gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_show_with_existing_tray_file(self) -> None:
        """Showing should list existing tray files."""
        # Create a tray.
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        tray.icon_name = 'phile-tray-empty'
        tray.text_icon = 'A'
        tray.save()
        # Show all tray icons. Pretend there are more than one.
        tray_2 = TrayFile(name='Disco', configuration=self.configuration)
        tray_2.icon_name = 'phile-tray-new'
        tray_2.text_icon = 'B'
        tray_2.save()
        # Throw in a file with a wrong suffix.
        (
            self.configuration.tray_directory /
            ('file' + self.configuration.tray_suffix + '_not')
        ).touch()
        # Also throw in a directory that should be ignored.
        (
            self.configuration.tray_directory /
            ('subdirectory' + self.configuration.tray_suffix)
        ).mkdir()
        # Need icon paths to test icon loading.
        set_icon_paths()
        # Check that they are all detected when showing the tray icons.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 2)
        self.assertTrue(gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        children = gui_icon_list.tray_children()
        self.assertEqual(children[0].icon().name(), tray_2.icon_name)
        self.assertEqual(children[1].icon().name(), tray.icon_name)

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_show_tray_file_without_icon_name_or_path(self) -> None:
        """Showing a tray file without icon should use default icon."""
        # Create a tray.
        tray = TrayFile(name='VeCat', configuration=self.configuration)
        tray.save()
        # Need icon paths to test icon loading.
        set_icon_paths()
        # Check that they are all detected when showing the tray icons.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertTrue(gui_icon_list._signal_emitter.is_started())
        self.assertTrue(
            gui_icon_list._file_system_monitor.was_start_called()
        )
        self.assertTrue(
            not gui_icon_list._file_system_monitor.was_stop_called()
        )
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        children = gui_icon_list.tray_children()
        self.assertEqual(
            children[0].icon().name(), self.configuration.tray_icon_name
        )

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_new_tray_file_creates_tray_icon(self) -> None:
        """Writing a new tray file creates a system tray icon."""
        # There should be no icons displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        # Need icon paths to test icon loading.
        set_icon_paths()
        # Detect when the handler from gui_icon_list will be dispatched.
        signal_emitter = self.gui_icon_list._signal_emitter
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        tray_file.save()
        self.assertTrue(tray_file.path.is_file())
        # Wait for watchdog to find it.
        signal_emitter.dispatch.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].icon().name(), tray_file.icon_name)

    def test_deleting_tray_file_destroys_tray_icon(self) -> None:
        """Removing a tray file destroys its tray icon."""
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        tray_file.save()
        self.assertTrue(tray_file.path.is_file())
        # Need icon paths to test icon loading.
        set_icon_paths()
        # There should be one icon displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        # Detect when the handler from gui_icon_list will be dispatched.
        signal_emitter = self.gui_icon_list._signal_emitter
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Wait for watchdog to notice the tray file is gone now.
        tray_file.remove()
        signal_emitter.dispatch.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme', q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon', SystemTrayIcon
    )
    def test_modifying_tray_file_updates_tray_icon(self) -> None:
        """Modifying a tray file updates its tray icon."""
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        tray_file.save()
        self.assertTrue(tray_file.path.is_file())
        # Need icon paths to test icon loading.
        set_icon_paths()
        # There should be one icon displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        # Detect when the handler from gui_icon_list will be dispatched.
        signal_emitter = self.gui_icon_list._signal_emitter
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Wait for watchdog to notice the tray file has been changed.
        tray_file.icon_name = 'phile-tray-empty'
        tray_file.save()
        signal_emitter.dispatch.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].icon().name(), tray_file.icon_name)

    def test_moving_tray_file_recreates_tray_icon(self) -> None:
        """Moving a tray file is treated as delete and create."""
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        tray_file.save()
        self.assertTrue(tray_file.path.is_file())
        # Need icon paths to test icon loading.
        set_icon_paths()
        # There should be one icon displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        # Detect when the handler from gui_icon_list will be dispatched.
        signal_emitter = self.gui_icon_list._signal_emitter
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Wait for watchdog to notice the tray file is moved now.
        new_name = 'Disco'
        new_tray_file = TrayFile(
            name=new_name, configuration=self.configuration
        )
        tray_file.path.rename(new_tray_file.path)
        signal_emitter.dispatch.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        self.assertListEqual(gui_icon_list.tray_files, [new_tray_file])

    def test_creating_deleting_tray_file_may_cause_nothing(self) -> None:
        """
        Created file may be deleted before processing.

        Nothing should be done in those cases,
        since the file content is not available anymore.
        """
        # There should be one icon displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        # Detect when the handler from gui_icon_list will be dispatched.
        signal_emitter = self.gui_icon_list._signal_emitter
        signal_emitter.dispatch = ThreadedMock(  # type: ignore
            target=signal_emitter.dispatch
        )
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        tray_file.save()
        self.assertTrue(tray_file.path.is_file())
        # Wait for watchdog to notice it.
        signal_emitter.dispatch.assert_called_soon()
        # Remove the tray file.
        tray_file.remove()
        self.assertTrue(not tray_file.path.is_file())
        # Wait for watchdog to notice it.
        signal_emitter.dispatch.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)


if __name__ == '__main__':
    unittest.main()
