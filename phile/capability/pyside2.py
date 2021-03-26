#!/usr/bin/env python3

# Standard libraries.
import collections.abc
import contextlib
import importlib.util
import platform
import subprocess
import typing

# Internal modules.
import phile.capability


def _is_gui_available() -> bool:
    if platform.system() == 'Windows':
        return True
    try:
        subprocess.run(
            ['xset', 'q'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def _is_pyside2_available() -> bool:
    return importlib.util.find_spec('PySide2') is not None


def is_available() -> bool:
    return _is_gui_available() and _is_pyside2_available()


def provide_qapplication_in(
    capability_registry: phile.capability.Registry
) -> contextlib.AbstractContextManager[typing.Any]:
    # Need to scope import to not always import PySide2.
    # pylint: disable=import-outside-toplevel import PySide2.QtCore
    import PySide2.QtGui
    import PySide2.QtWidgets
    qt_app = PySide2.QtWidgets.QApplication()
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            capability_registry.provide(
                qt_app, PySide2.QtCore.QCoreApplication
            )
        )
        stack.enter_context(
            capability_registry.provide(
                qt_app, PySide2.QtGui.QGuiApplication
            )
        )
        stack.enter_context(capability_registry.provide(qt_app))
        return stack.pop_all()
    assert False, 'Unreachable code'


def stop() -> None:
    # Need to scope import to not always import PySide2.
    # pylint: disable=import-outside-toplevel
    import PySide2.QtCore
    import phile.PySide2.QtCore  # pylint: disable=redefined-outer-name
    qt_app = PySide2.QtCore.QCoreApplication.instance()
    phile.PySide2.QtCore.call_soon_threadsafe(qt_app.quit)


def run(capability_registry: phile.capability.Registry) -> None:
    # Need to scope import to not always import PySide2.
    # pylint: disable=import-outside-toplevel
    import PySide2.QtCore
    QCoreApplication = PySide2.QtCore.QCoreApplication
    qt_app = capability_registry[QCoreApplication]
    qt_app.exec_()
