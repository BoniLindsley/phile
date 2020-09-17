#!/usr/bin/env python3
"""
----------------------
Test phile.trigger GUI
----------------------
"""

# Standard library.
import datetime
import logging
import unittest

# External dependencies.
from PySide2.QtCore import QEventLoop, Qt
from PySide2.QtWidgets import QMdiArea

# Internal packages.
from phile.notify.gui import NotificationMdi, NotificationMdiSubWindow
from test_phile.pyside2_test_tools import QTestApplication

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestNotificationMdiSubWindow(unittest.TestCase):
    """
    Unit test for :class:`~phile.notify.gui.NotificationMdiSubWindow`.
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
        self.app = QTestApplication()
        self.content = 'You have 123 friends.\n'
        'You have 456 unread messages.\n'
        'New security settings has been added.\n'
        'Log in to review them.',
        self.creation_datetime = datetime.datetime(
            year=2000,
            month=11,
            day=2,
            hour=10,
            minute=3,
            second=58,
            microsecond=4,
        )
        self.name = 'VaceBook'
        self.notification_sub_window = NotificationMdiSubWindow(
            content=self.content,
            creation_datetime=self.creation_datetime,
            name=self.name,
        )

    def tearDown(self) -> None:
        """
        Shutdown PySide2 application after each method test.

        PySide2 Applications act as singletons.
        Any previous instances must be shutdown
        before a new one can be created.
        """
        self.app.tear_down()

    def test_initialisation(self) -> None:
        """Create a NotificationMdiSubWindow object."""
        # The object is created in `setUp`.
        # This tests flags up whether the constructor itself fails.
        notification_sub_window = self.notification_sub_window
        # Check the parameters given in the constructor.
        self.assertEqual(notification_sub_window.content, self.content)
        self.assertEqual(
            notification_sub_window.creation_datetime,
            self.creation_datetime
        )
        self.assertEqual(notification_sub_window.name, self.name)
        # It should not be marked as read by default.
        self.assertTrue(not notification_sub_window.is_read)

    def test_content(self) -> None:
        """Check that content set requests are processed."""
        notification_sub_window = self.notification_sub_window
        new_content = 'This is not content.'
        notification_sub_window.content = new_content
        self.assertEqual(notification_sub_window.content, new_content)

    def test_creation_datetime(self) -> None:
        """Check that creation datetime set requests are processed."""
        notification_sub_window = self.notification_sub_window
        new_creation_datetime = datetime.datetime(
            year=1999, month=9, day=9
        )
        notification_sub_window.creation_datetime = new_creation_datetime
        self.assertEqual(
            notification_sub_window.creation_datetime,
            new_creation_datetime
        )

    def test_event_handling_without_parent_mdi(self) -> None:
        """Check that basic events are processed without issues."""
        notification_sub_window = self.notification_sub_window
        notification_sub_window.showMaximized()
        notification_sub_window.hide()

    def test_is_read(self) -> None:
        """Check that mark as read requests are processed."""
        notification_sub_window = self.notification_sub_window
        notification_sub_window.is_read = True
        self.assertTrue(notification_sub_window.is_read)
        notification_sub_window.is_read = False
        self.assertTrue(not notification_sub_window.is_read)

    def test_name(self) -> None:
        """Check that content path set requests are processed."""
        notification_sub_window = self.notification_sub_window
        new_name = 'What title?'
        notification_sub_window.name = new_name
        self.assertEqual(notification_sub_window.name, new_name)


class TestNotificationMdi(unittest.TestCase):
    """
    Unit test for :class:`~phile.notify.gui.NotificationMdi`.
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
        self.app = QTestApplication()
        self.notification_mdi = NotificationMdi()

    def tearDown(self) -> None:
        """
        Shutdown PySide2 application after each method test.

        PySide2 Applications act as singletons.
        Any previous instances must be shutdown
        before a new one can be created.
        """
        self.notification_mdi.deleteLater()
        self.app.tear_down()

    def test_initialisation(self) -> None:
        """Create a NotificationMdiSubWindow object."""
        # The object is created in `setUp`.
        # This tests flags up whether the constructor itself fails.

    def test_show_and_hide(self) -> None:
        """Make sure both showing re-tiles but hiding does not."""
        notification_mdi = self.notification_mdi

        _logger.debug('Creating sub-window 1.')
        notification_sub_window = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
                hour=11,
                minute=4,
                second=59,
                microsecond=5,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 1)

        # This triggers resize events which re-tiles.
        # We want to test that adding and showing a sub-window re-tiles.
        # This is to make sure the retile we get later
        # is from adding a sub-window.
        _logger.debug('Showing the MDI.')
        notification_mdi.show()
        self.assertEqual(notification_sub_window.pos().x(), 0)

        # Move the sub-window.
        # It will be checked later that it is moved.
        _logger.debug('Moving sub-window 1.')
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)
        # Test hiding first since setting up has already shown the MDI.
        # There is no point in repositioning when hiding.
        _logger.debug('Hiding MDI.')
        notification_mdi.hide()
        self.assertEqual(notification_sub_window.pos().x(), 1)

        # Try showing it again.
        _logger.debug('Moving sub-window 1.')
        self.assertEqual(notification_sub_window.pos().x(), 1)
        # This time there shouls be a re-tiling.
        _logger.debug('Showing MDI.')
        notification_mdi.show()
        self.assertEqual(notification_sub_window.pos().x(), 0)

    def test_show_and_hide_sub_window(self) -> None:
        """Make sure both showing and hiding a sub-window retiles."""
        notification_mdi = self.notification_mdi

        _logger.debug('Creating sub-window 1.')
        notification_sub_window = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
                hour=11,
                minute=4,
                second=59,
                microsecond=5,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 1)

        # This triggers resize events which re-tiles.
        # We want to test that adding and showing a sub-window re-tiles.
        # This is to make sure the retile we get later
        # is from adding a sub-window.
        _logger.debug('Showing the MDI.')
        notification_mdi.show()

        # Move the sub-window.
        # It will be checked later that it is moved.
        _logger.debug('Moving sub-window 1.')
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)

        # We cannot tell whether the adding the first sub-window
        # did activate a re-tile or not
        # since the first sub-window typically goes to the top left.
        # Adding another sub-window should trigger a re-tile
        # and move the first sub-window back to the top left.
        _logger.debug('Creating sub-window 2.')
        notification_sub_window_2 = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 2)
        _logger.debug('Showing sub-window 2.')
        notification_sub_window_2.show()
        self.assertEqual(notification_sub_window.pos().x(), 0)

        # Move the sub-window.
        # It will be checked later that it is moved.
        _logger.debug('Moving sub-window 1.')
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)

        _logger.debug('Hiding sub-window 2.')
        notification_sub_window_2.hide()
        self.assertEqual(notification_sub_window.pos().x(), 0)

    def test_close_sub_window(self) -> None:
        """Closing sub-window retiles."""

        _logger.debug('Creating MDI.')
        notification_mdi = self.notification_mdi

        _logger.debug('Creating sub-window 1.')
        notification_sub_window = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
                hour=11,
                minute=4,
                second=59,
                microsecond=5,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        _logger.debug('Creating sub-window 2.')
        notification_sub_window_2 = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 2)

        # Showing the MDI triggers resize event which retiles.
        # Also showing after adding sub-windows to the MDI changes
        # current active window, if any, from active to inactive
        # and the newly added sub-window from inactive to active.
        # These appear as window state change events.
        # Every change also queues events into the event queue.
        # They are all processed when showing the MDI.
        _logger.debug('Showing the MDI.')
        notification_mdi.show()

        # Move the sub-window.
        # It will be checked later that it will be moved again.
        _logger.debug('Moving sub-window 1.')
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)
        # Check that closing the window re-tiles.
        # Closing the window `deleteLater` the window.
        # Handle the event to trigger retiling.
        _logger.debug('Closing sub-window 2.')
        notification_sub_window_2.close()
        _logger.debug('Draining event queue.')
        self.app.process_deferred_delete_events()
        self.assertEqual(notification_sub_window.pos().x(), 0)

    def test_maximise_and_minimise_sub_window(self) -> None:
        """Maximising and minimising a sub-window should re-tile."""
        notification_mdi = self.notification_mdi
        notification_sub_window = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
                hour=11,
                minute=4,
                second=59,
                microsecond=5,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 1)

        # Create a second window to check that it will later get re-tiled
        # when the first one will be maximised.
        notification_sub_window_2 = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 2)

        # Showing the MDI triggers resize event which retiles.
        # The steps here is to get these events out of the way,
        # to make sure that the retile we get later
        # will really be from the maximising.
        notification_mdi.show()
        self.assertEqual(notification_sub_window.pos().x(), 0)
        self.assertEqual(notification_sub_window_2.pos().x(), 0)
        # Empty the event queue.
        self.app.process_events()
        self.assertEqual(notification_sub_window.pos().x(), 0)
        self.assertEqual(notification_sub_window_2.pos().x(), 0)

        # Move the second sub-window.
        notification_sub_window_2.resize(0, 0)
        notification_sub_window_2.move(1, 1)
        self.assertEqual(notification_sub_window_2.pos().x(), 1)
        # Maximise the first sub-window and check that a retile occured.
        notification_sub_window.showMaximized()
        self.assertEqual(notification_sub_window_2.pos().x(), 0)

        # Do the same with minimising.
        # Empty the event queue.
        self.app.process_events()
        self.assertEqual(notification_sub_window.pos().x(), 0)
        self.assertEqual(notification_sub_window_2.pos().x(), 0)
        # Move the second sub-window.
        notification_sub_window_2.resize(0, 0)
        notification_sub_window_2.move(1, 1)
        self.assertEqual(notification_sub_window_2.pos().x(), 1)
        # Minimise and check.
        notification_sub_window.showMinimized()
        self.assertEqual(notification_sub_window_2.pos().x(), 0)

    def test_resizeEvent(self) -> None:
        """Resizing should retile sub-windows."""
        notification_mdi = self.notification_mdi
        notification_sub_window = notification_mdi.add_notification(
            name='WatZap',
            creation_datetime=datetime.datetime(
                year=2001,
                month=12,
                day=3,
                hour=11,
                minute=4,
                second=59,
                microsecond=5,
            ),
            content='You have 234 friends.\n'
            'You have 5678 messages.'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 1)

        # Showing the MDI triggers resize event which retiles.
        # But we cannot tell whether other events also triggers it,
        # though there should not be.
        # So we will check later that a retile is triggered
        # with a manual resize.
        # The steps here is to make sure that the retile we get later
        # is really from a resize.
        notification_mdi.show()
        self.assertEqual(notification_sub_window.pos().x(), 0)
        # Process all events so we know the re-tile
        # will only be from the resize.
        self.app.process_events()
        self.assertEqual(notification_sub_window.pos().x(), 0)

        # Move the sub-window
        # and check that it is re-tiled after a resize.
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)
        # Trigger a resize and check that a retile occured.
        mdi_size = notification_mdi.size()
        notification_mdi.resize(mdi_size.width() - 1, mdi_size.height())
        self.assertEqual(notification_sub_window.pos().x(), 0)

    def test_resizeEvent_in_tabbed_view_mode(self) -> None:
        """No retiling should happen in tabbed view mode."""
        notification_mdi = self.notification_mdi
        _logger.debug('Changing the MDI to tabbed view.')
        notification_mdi.setViewMode(QMdiArea.TabbedView)
        _logger.debug('Creating sub-window.')
        notification_sub_window = notification_mdi.add_notification(
            name='VeeCat',
            creation_datetime=datetime.datetime(
                year=2002,
                month=1,
                day=5,
            ),
            content='You have 1 friend(s).\n'
        )
        self.assertEqual(len(notification_mdi.subWindowList()), 1)

        # Move the sub-window.
        # It will be checked later that it will not be moved by `show()`.
        _logger.debug('Moving sub-window.')
        notification_sub_window.resize(0, 0)
        notification_sub_window.move(1, 1)
        self.assertEqual(notification_sub_window.pos().x(), 1)

        # When showing the window, the MDI receives a resize event,
        # which in sub-window mode should re-tile,
        # and that is tested in another test method.
        # Re-tiling should not happen here though
        # because the MDI is in tabbed view mode.
        _logger.debug('Showing the MDI.')
        notification_mdi.show()
        self.assertEqual(notification_sub_window.pos().x(), 1)


if __name__ == '__main__':
    unittest.main()
