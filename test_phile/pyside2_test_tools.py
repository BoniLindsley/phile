#!/usr/bin/env python3
"""
----------------------
test_phile.PySide2.QtWidgts
----------------------
"""

# Standard libraries.
import datetime
import os
import tempfile
import typing

# External dependencies.
import PySide2.QtCore
import PySide2.QtWidgets


class EnvironBackup:

    def __init__(self):
        self._source_dict = os.environ
        self._backup_dict: typing.Dict[str, typing.Optional[str]] = {}

    def restore(self):
        source_dict = self._source_dict
        for key, value in self._backup_dict.items():
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value

    def backup_and_set(self, **kwargs):
        backup_dict = self._backup_dict
        source_dict = self._source_dict
        for key, value in kwargs.items():
            backup_dict[key] = source_dict.get(key)
            if value is None:
                source_dict.pop(key, None)
            else:
                source_dict[key] = value


class QTestApplication(PySide2.QtWidgets.QApplication):

    def __init__(
        self,
        process_event_wait_time: datetime.timedelta = datetime.timedelta(
            seconds=2
        ),
        set_xdg_runtime_dir: bool = True,
        set_qt_qpa_platform: bool = True,
        *args,
        **kwargs
    ):
        self.__process_event_wait_time_ = process_event_wait_time
        environ_backup = EnvironBackup()
        self.__xdg_runtime_dir_ = None
        if set_xdg_runtime_dir:
            self.__xdg_runtime_dir_ = tempfile.TemporaryDirectory()
            environ_backup.backup_and_set(
                XDG_RUNTIME_DIR=self.__xdg_runtime_dir_.name
            )
        if set_qt_qpa_platform:
            environ_backup.backup_and_set(QT_QPA_PLATFORM='offscreen')
        self.__environ_backup_ = environ_backup
        super().__init__(*args, **kwargs)

    def __del__(self):
        if self.__xdg_runtime_dir_ is not None:
            self.__xdg_runtime_dir_.cleanup()
        self.__environ_backup_.restore()

    def process_deferred_delete_events(self):
        # Calling `processEvents`
        # does not process `DeferredDelete` events.
        # Asking `sendPostedEvents` to process all events
        # (which done by`processEvents`, I think)
        # also does not process it.
        # So this needs to be explicitly called.
        self.__class__.sendPostedEvents(
            None, PySide2.QtCore.QEvent.DeferredDelete
        )

    def process_events(self):
        self.__class__.processEvents(
            PySide2.QtCore.QEventLoop.AllEvents,
            int(
                self.__process_event_wait_time_ /
                datetime.timedelta(milliseconds=1)
            )
        )

    def tear_down(self):
        # Destructor clean-up process.
        # While it would be great to have this in `__del__`,
        # Python3 does not guarantee when the finaliser is called.
        # So we have an explicit clean-up method here instead.
        self.process_events()
        self.process_deferred_delete_events()
        self.shutdown()
