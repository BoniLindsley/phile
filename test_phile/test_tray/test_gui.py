#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.tray.gui`
--------------------------
"""

# Standard library.
import pathlib
import pkg_resources
import tempfile
import unittest
import unittest.mock

# External dependencies.
from PySide2.QtGui import QIcon
import watchdog.events
import watchdog.observers

# Internal packages.
import phile
import phile.PySide2
import phile.PySide2.QtGui
import phile.PySide2.QtWidgets
import phile.tray
import phile.tray.gui
from phile.tray.gui import set_icon_paths
import test_phile.threaded_mock
from test_phile.test_PySide2.test_QtWidgets import UsesQApplication


class TestSetIconPaths(UsesQApplication, unittest.TestCase):
    """Tests :class:`~phile.tray.set_icon_paths`."""

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


class TestGuiIconList(UsesQApplication, unittest.TestCase):
    """Tests :class:`~phile.tray.gui.GuiIconList`."""

    def set_up_configuration(self) -> None:
        """
        Use unique data directories to not interfere with other tests.
        """
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        self.trigger_directory = (
            self.configuration.trigger_root / 'phile-tray-gui'
        )

    def set_up_observer(self) -> None:
        """
        Use unique observers to ensure handlers do not linger.

        Start immediately to allow file changes propagate.
        The observer does not join, as that can take a long time.
        """
        self.watching_observer = observer = watchdog.observers.Observer()
        observer.daemon = True
        observer.start()
        self.addCleanup(observer.stop)

    def set_up_gui(self) -> None:
        """Create the gui being tested."""
        self.gui_icon_list = phile.tray.gui.GuiIconList(
            configuration=self.configuration,
            watching_observer=self.watching_observer,
        )
        # Use a lambda to allow the reference to be replaced.
        self.addCleanup(lambda: self.gui_icon_list.deleteLater())

    def set_up_tray_dispatcher(self) -> None:
        """Patch for detecting when tray dispatch has been called."""
        scheduler = self.gui_icon_list._tray_scheduler
        self.tray_path_handler_patch = unittest.mock.patch.object(
            scheduler,
            'path_handler',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=scheduler.path_handler
        )

    def set_up_trigger_dispatcher(self) -> None:
        """Patch for detecting when trigger dispatch has been called."""
        scheduler = self.gui_icon_list._trigger_scheduler
        self.trigger_path_handler_patch = unittest.mock.patch.object(
            scheduler,
            'path_handler',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=scheduler.path_handler
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        super().setUp()
        self.set_up_gui()
        self.set_up_tray_dispatcher()
        self.set_up_trigger_dispatcher()

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
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon',
        phile.PySide2.QtWidgets.OffscreenSystemTrayIcon
    )
    def test_show_and_hide(self) -> None:
        """Showing and hiding should apply to its tray icons."""
        # Create a tray.
        tray = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
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
        trigger_directory = self.trigger_directory
        trigger_suffix = self.configuration.trigger_suffix
        trigger_path = trigger_directory / ('show' + trigger_suffix)
        # Respond to a show trigger.
        with self.trigger_path_handler_patch as handler_mock:
            trigger_path.unlink()
            handler_mock.assert_called_with_soon(trigger_path)
            phile.PySide2.process_events()
            self.assertTrue(not gui_icon_list.is_hidden())
        # Respond to a hide trigger.
        trigger_path = trigger_directory / ('hide' + trigger_suffix)
        with self.trigger_path_handler_patch as handler_mock:
            trigger_path.unlink()
            handler_mock.assert_called_with_soon(trigger_path)
            phile.PySide2.process_events()
            self.assertTrue(gui_icon_list.is_hidden())
        # Respond to a close trigger.
        trigger_path = trigger_directory / ('close' + trigger_suffix)
        with self.trigger_path_handler_patch as handler_mock:
            trigger_path.unlink()
            handler_mock.assert_called_with_soon(trigger_path)
            phile.PySide2.process_events()
            self.assertTrue(
                not gui_icon_list._trigger_scheduler.is_scheduled
            )
        # Give cleanup something to delete.
        self.gui_icon_list = unittest.mock.Mock()

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    def test_load_icon_from_name(self) -> None:
        """Retrive icon based on a icon name in tray file data."""
        # Create a tray.
        tray = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
        resource_dir_path = pathlib.Path(
            pkg_resources.resource_filename('phile.tray', "resources")
        )
        tray.icon_name = 'phile-tray-empty'
        set_icon_paths()
        gui_icon_list = self.gui_icon_list
        new_icon = gui_icon_list.load_icon(tray)
        self.assertTrue(not new_icon.isNull())
        self.assertEqual(new_icon.name(), tray.icon_name)

    def test_load_icon_from_path(self) -> None:
        """Retrive icon based on a icon path in tray file data."""
        # Create a tray.
        tray = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
        resource_dir_path = pathlib.Path(
            pkg_resources.resource_filename('phile.tray', "resources")
        )
        tray.icon_path = (
            resource_dir_path / 'icons' / 'blank' / '64x64' / 'status' /
            'phile-tray-empty.png'
        )
        # Try to get an icon.
        gui_icon_list = self.gui_icon_list
        new_icon = gui_icon_list.load_icon(tray)
        self.assertTrue(not new_icon.isNull())

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon',
        phile.PySide2.QtWidgets.OffscreenSystemTrayIcon
    )
    def test_show_tray_file_without_icon_name_or_path(self) -> None:
        """Showing a tray file without icon should use default icon."""
        # Create a tray.
        tray = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
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
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon',
        phile.PySide2.QtWidgets.OffscreenSystemTrayIcon
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
        tray_file = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        # Wait for watchdog to find it.
        with self.tray_path_handler_patch as handler_mock:
            tray_file.save()
            self.assertTrue(tray_file.path.is_file())
            handler_mock.assert_called_with_soon(tray_file.path)
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].icon().name(), tray_file.icon_name)

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon',
        phile.PySide2.QtWidgets.OffscreenSystemTrayIcon
    )
    def test_prepend_new_tray_icon(self) -> None:
        """Handle icon shift if new tray icon has high priority."""
        self.test_new_tray_file_creates_tray_icon()
        # There should be no icons displayed at the beginning.
        gui_icon_list = self.gui_icon_list
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        # Create the tray file.
        tray_file = phile.tray.File.from_path_stem(
            path_stem='FeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        # Wait for watchdog to find it.
        with self.tray_path_handler_patch as handler_mock:
            tray_file.save()
            self.assertTrue(tray_file.path.is_file())
            handler_mock.assert_called_with_soon(tray_file.path)
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        self.assertListEqual(
            [
                child.icon().name()
                for child in gui_icon_list.tray_children()
            ],
            ['phile-tray-new', tray_file.icon_name],
        )

    def test_deleting_tray_file_destroys_tray_icon(self) -> None:
        """Removing a tray file destroys its tray icon."""
        # Create the tray file.
        tray_file = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
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
        with self.tray_path_handler_patch as handler_mock:
            tray_file.path.unlink(missing_ok=True)
            handler_mock.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)

    @unittest.mock.patch(
        'phile.tray.gui.QIcon.fromTheme',
        phile.PySide2.QtGui.q_icon_from_theme
    )
    @unittest.mock.patch(
        'phile.tray.gui.QSystemTrayIcon',
        phile.PySide2.QtWidgets.OffscreenSystemTrayIcon
    )
    def test_modifying_tray_file_updates_tray_icon(self) -> None:
        """Modifying a tray file updates its tray icon."""
        # Create the tray file.
        tray_file = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
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
        with self.tray_path_handler_patch as handler_mock:
            tray_file.save()
            handler_mock.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        children = gui_icon_list.tray_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].icon().name(), tray_file.icon_name)

    def test_moving_tray_file_recreates_tray_icon(self) -> None:
        """Moving a tray file is treated as delete and create."""
        # Create the tray file.
        tray_file = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
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
        new_tray_file = phile.tray.File.from_path_stem(
            path_stem=new_name, configuration=self.configuration
        )
        with self.tray_path_handler_patch as handler_mock:
            tray_file.path.rename(new_tray_file.path)
            handler_mock.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 1)
        self.assertListEqual(
            gui_icon_list._tray_sorter.tracked_data, [new_tray_file]
        )

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
        tray_file = phile.tray.File.from_path_stem(
            path_stem='VeCat', configuration=self.configuration
        )
        self.assertTrue(not tray_file.path.is_file())
        tray_file.icon_name = 'phile-tray-new'
        # Wait for watchdog to notice it.
        with self.tray_path_handler_patch as handler_mock:
            tray_file.save()
            self.assertTrue(tray_file.path.is_file())
            handler_mock.assert_called_soon()
        # Remove the tray file.
        # Wait for watchdog to notice it.
        with self.tray_path_handler_patch as handler_mock:
            tray_file.path.unlink(missing_ok=True)
            self.assertTrue(not tray_file.path.is_file())
            handler_mock.assert_called_soon()
        # The Qt event should be posted by now.
        # The icon list should hve handled it by creating a tray icon.
        phile.PySide2.process_events()
        self.assertEqual(len(gui_icon_list.tray_children()), 0)


if __name__ == '__main__':
    unittest.main()
