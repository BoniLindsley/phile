#!/usr/bin/env python3

# Standard library.
import datetime
import logging
import sys

# External dependencies.
from PySide2.QtWidgets import QApplication, QMainWindow

# Internal packages.
from phile.notify.gui import NotificationMdi, NotificationMdiSubWindow

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


def main(argv) -> int:  # pragma: no cover
    logging.basicConfig(
        handlers=[logging.StreamHandler()], level=logging.DEBUG
    )

    # A QCoreApplication must be created before any QObjects are.
    _logger.debug('Creating Qt application.')
    app = QApplication(argv)

    _logger.debug('Creating MDI.')
    notification_mdi = NotificationMdi()
    _logger.debug('Showing MDI.')
    notification_mdi.show()

    _logger.debug('Adding sub-window 1.')
    sub_window = notification_mdi.add_notification(
        name='Skip',
        creation_datetime=datetime.datetime(year=2003, month=8, day=29),
        content='What is MSN messenger? Lync?'
        ' Or rather, what is Linux? Actually what is Firefox?'
    )
    _logger.debug('Showing sub-window 1.')
    sub_window.show()

    _logger.debug('Adding sub-window 2.')
    sub_window = notification_mdi.add_notification(
        name='VaseBroke',
        creation_datetime=datetime.datetime(year=2004, month=2, day=4),
        content='You have 0 unread message(s).\n'
        'You have 1 friend(s). Probably.\n'
        'New ad, I mean, security settings had been added.\n'
        'Log in to review them.',
    )
    _logger.debug('Showing sub-window 2.')
    sub_window.show()

    _logger.debug('Adding sub-window 3.')
    sub_window = notification_mdi.add_notification(
        name='VeCat',
        creation_datetime=datetime.datetime(year=2011, month=1, day=21),
        content='We have everything!\n'
        'VeBlank, VeEat, VeLive and VeMon!\n'
        'And, we are banned.'
    )
    _logger.debug('Showing sub-window 3.')
    sub_window.show()

    _logger.debug('Adding sub-window 4.')
    sub_window = notification_mdi.add_notification(
        name='MissChord',
        creation_datetime=datetime.datetime(year=2015, month=5, day=13),
        content='Skype? Is this 2005?\n'
        'Trying to be Steam? I do not know what you mean.'
    )
    _logger.debug('Showing sub-window 4.')
    sub_window.show()

    #main_window = QMainWindow()
    #main_window.setCentralWidget(notification_mdi)
    #main_window.show()

    _logger.debug('Running Qt event loop.')
    return app.exec_()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
