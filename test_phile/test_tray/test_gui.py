#!/usr/bin/env python3
"""
-------------------
Test phile.tray GUI
-------------------
"""

# Standard library.
import logging
import pathlib
import pkg_resources
import tempfile
import unittest
import unittest.mock

# External dependencies.
from PySide2.QtGui import QIcon
import watchdog.events  # type: ignore[import]
from watchdog.observers import Observer  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray.gui
from phile.tray.gui import set_icon_paths
from phile.tray.tray_file import TrayFile
import phile.watchdog_extras
from test_phile.pyside2_test_tools import (
    QTestApplication, q_icon_from_theme, SystemTrayIcon
)
import test_phile.threaded_mock

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestSetIconPaths(unittest.TestCase):
    """Tests :class:`~phile.tray.set_icon_paths`."""

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        app = QTestApplication()
        self.addCleanup(app.tear_down)

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
    """Tests :class:`~phile.tray.gui.GuiIconList`."""

    def setUp(self) -> None:
        """
        Create a PySide2 application before each method test.

        It has to be created to do initialisation
        for GUI widgets to work.
        A new one is created for each test
        to make sure no application state information
        would interfere with each other.
        """
        # Unique data directory to not interfere with other tests.
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        # PySide2 app has to be cleaned up properly.
        self.app = QTestApplication()
        self.addCleanup(self.app.tear_down)
        # Unique observers to ensure handlers do not inger.
        # Start immediately to allow file changes propagate.
        # Using a custom observer instead of allowing ``GuiIconList``
        # to automatically create one
        # because it would try to ``stop`` and ``join``
        # and we do not care about that for most tests.
        self.watching_observer = Observer()
        self.watching_observer.daemon = True
        self.watching_observer.start()
        self.addCleanup(self.watching_observer.stop)
        # Actually create the ``GuiIconList``.
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        self.gui_icon_list = phile.tray.gui.GuiIconList(
            configuration=self.configuration,
            watching_observer=self.watching_observer,
        )
        # Use a lambda to allow `self.main_window` to be replaced.
        self.addCleanup(lambda: self.gui_icon_list.deleteLater())
        # For detecting whether dispatch has been called.
        dispatcher = self.gui_icon_list._tray_scheduler._watchdog_handler
        self.dispatch_patch = unittest.mock.patch.object(
            dispatcher,
            'dispatch',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=dispatcher.dispatch,
        )
        self.trigger_directory = (
            self.configuration.trigger_root / 'phile-tray-gui'
        )

    def test_setup_and_teardown(self) -> None:
        """Flags up set up and tear down issues."""
        # The object is created in `setUp`.
        # This tests flags up whether the constructor itself fails.
        gui_icon_list = self.gui_icon_list
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(gui_icon_list.is_hidden())
        self.assertTrue((
            self.configuration.trigger_root / 'phile-tray-gui' /
            ('close' + self.configuration.trigger_suffix)
        ).is_file())
        self.assertTrue((
            self.configuration.trigger_root / 'phile-tray-gui' /
            ('show' + self.configuration.trigger_suffix)
        ).is_file())

    def test_show_and_hide_without_tray_icons(self) -> None:
        """Showing and hiding should start and stop file monitoring."""
        # Showing should start monitoring.
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list.is_hidden())
        self.assertTrue((
            self.configuration.trigger_root / 'phile-tray-gui' /
            ('hide' + self.configuration.trigger_suffix)
        ).is_file())
        # Hiding should stop monitoring.
        # This should be done by stopping the emitter
        # and not the file system monitor
        # so that the monitor can be started up again if necessary.
        gui_icon_list.hide()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(gui_icon_list.is_hidden())
        self.assertTrue((
            self.configuration.trigger_root / 'phile-tray-gui' /
            ('show' + self.configuration.trigger_suffix)
        ).is_file())
        # Try to show again to ensure toggling works.
        gui_icon_list.show()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(not gui_icon_list.is_hidden())
        self.assertTrue((
            self.configuration.trigger_root / 'phile-tray-gui' /
            ('hide' + self.configuration.trigger_suffix)
        ).is_file())

    def test_hide_without_show(self) -> None:
        """Calling hide without showing should just not do anything."""
        gui_icon_list = self.gui_icon_list
        gui_icon_list.hide()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)
        self.assertTrue(gui_icon_list.is_hidden())

    def test_show_shown_list(self) -> None:
        """Calling show on a shown list should just do nothing."""
        gui_icon_list = self.gui_icon_list
        gui_icon_list.show()
        self.assertTrue(not gui_icon_list.is_hidden())
        gui_icon_list.show()
        self.assertTrue(not gui_icon_list.is_hidden())

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
        self.assertTrue(not gui_icon_list.is_hidden())
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertTrue(children[0].isVisible())
        # Hiding should stop monitoring.
        # This should be done by stopping the emitter
        # and not the file system monitor
        # so that the monitor can be started up again if necessary.
        gui_icon_list.hide()
        self.assertTrue(gui_icon_list.is_hidden())
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertTrue(not children[0].isVisible())

    def test_triggers(self) -> None:
        """Tray GUI has show, hide and close triggers."""
        gui_icon_list = self.gui_icon_list
        # Use a threaded mock to check when events are queued into Qt.
        dispatcher = gui_icon_list._trigger_scheduler._watchdog_handler
        dispatch_patch = unittest.mock.patch.object(
            dispatcher,
            'dispatch',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=dispatcher.dispatch,
        )
        trigger_directory = self.trigger_directory
        trigger_suffix = self.configuration.trigger_suffix
        trigger_path = trigger_directory / ('show' + trigger_suffix)
        # Respond to a show trigger.
        with unittest.mock.patch.object(
            gui_icon_list, 'show', wraps=gui_icon_list.show
        ) as show_mock, dispatch_patch as dispatch_mock:
            trigger_path.unlink()
            dispatch_mock.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(str(trigger_path))
            )
            self.app.process_events()
            show_mock.assert_called()
        # Respond to a hide trigger.
        trigger_path = trigger_directory / ('hide' + trigger_suffix)
        with unittest.mock.patch.object(
            gui_icon_list, 'hide', wraps=gui_icon_list.hide
        ) as hide_mock, dispatch_patch as dispatch_mock:
            trigger_path.unlink()
            dispatch_mock.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(str(trigger_path))
            )
            self.app.process_events()
            hide_mock.assert_called()
        # Do not respond to an unknown trigger.
        # Cannot really test that it has no side effects.
        # Just run it for coverage to ensure it does not error.
        # Cannot mock process_trigger since its reference is given
        # to a wrapping handler.
        # So mocking the method does not replace it.
        trigger_name = 'unknown'
        trigger_path = trigger_directory / (
            trigger_name + trigger_suffix
        )
        with dispatch_patch as dispatch_mock:
            # Create the fake trigger.
            # Make sure appropriate events are processed.
            trigger_path.touch()
            dispatch_mock.assert_called_with_soon(
                watchdog.events.FileCreatedEvent(str(trigger_path))
            )
            self.app.process_events()
            dispatch_mock.reset_mock()
            # Activate the fake trigger.
            # It should still be detected.
            trigger_path.unlink()
            dispatch_mock.assert_called_with_soon(
                watchdog.events.FileDeletedEvent(str(trigger_path))
            )
            with self.assertLogs(
                logger='phile.tray.gui', level=logging.WARNING
            ) as logs:
                self.app.process_events()
        # Respond to a close trigger.
        trigger_path = trigger_directory / ('close' + trigger_suffix)
        with unittest.mock.patch.object(
            gui_icon_list, 'close', wraps=gui_icon_list.close
        ) as close_mock, dispatch_patch as dispatch_mock:
            trigger_path.unlink()
            dispatch_mock.assert_called_soon(
                watchdog.events.FileDeletedEvent(str(trigger_path))
            )
            self.app.process_events()
            close_mock.assert_called()
        # Give cleanup something to delete.
        self.gui_icon_list = unittest.mock.Mock()

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
        with self.assertLogs(
            logger='phile.tray.gui', level=logging.WARNING
        ) as logs:
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
        self.assertTrue(not gui_icon_list.is_hidden())
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
        self.assertTrue(not gui_icon_list.is_hidden())
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
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        # Wait for watchdog to find it.
        with self.dispatch_patch as dispatch_mock:
            tray_file.save()
            self.assertTrue(tray_file.path.is_file())
            dispatch_mock.assert_called_soon()
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
        # Wait for watchdog to notice the tray file is gone now.
        with self.dispatch_patch as dispatch_mock:
            tray_file.remove()
            dispatch_mock.assert_called_soon()
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
        # Wait for watchdog to notice the tray file has been changed.
        tray_file.icon_name = 'phile-tray-empty'
        with self.dispatch_patch as dispatch_mock:
            tray_file.save()
            dispatch_mock.assert_called_soon()
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
        # Wait for watchdog to notice the tray file is moved now.
        new_name = 'Disco'
        new_tray_file = TrayFile(
            name=new_name, configuration=self.configuration
        )
        with self.dispatch_patch as dispatch_mock:
            tray_file.path.rename(new_tray_file.path)
            dispatch_mock.assert_called_soon()
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
        # Create the tray file.
        tray_file = TrayFile(
            name='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        # Wait for watchdog to notice it.
        with self.dispatch_patch as dispatch_mock:
            tray_file.save()
            self.assertTrue(tray_file.path.is_file())
            dispatch_mock.assert_called_soon()
        # Remove the tray file.
        # Wait for watchdog to notice it.
        with self.dispatch_patch as dispatch_mock:
            tray_file.remove()
            self.assertTrue(not tray_file.path.is_file())
            dispatch_mock.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        self.app.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)


if __name__ == '__main__':
    unittest.main()
