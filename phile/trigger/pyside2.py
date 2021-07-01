#!/usr/bin/env python3

# Standard libraries.
import functools
import typing

# External dependencies.
import PySide2.QtGui
import PySide2.QtWidgets

# Internal modules.
import phile.PySide2.QtCore
import phile.trigger


class TriggerControlled:

    def __init__(
        self,
        *args: typing.Any,
        pyside2_executor: phile.PySide2.QtCore.Executor,
        trigger_prefix: str,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        assert widget.isWidgetType()  # pylint: disable=no-member
        self._trigger_prefix = trigger_prefix
        self.trigger_producer = phile.trigger.Provider(
            callback_map={
                self._trigger_prefix + '.show':
                    functools.partial(
                        pyside2_executor.submit,
                        widget.show,  # pylint: disable=no-member
                    ),
                self._trigger_prefix + '.hide':
                    functools.partial(
                        pyside2_executor.submit,
                        widget.hide,  # pylint: disable=no-member
                    ),
            },
            registry=trigger_registry
        )
        self.trigger_producer.bind()
        self.trigger_producer.show(self._trigger_prefix + '.show')

    def closeEvent(self, event: PySide2.QtGui.QCloseEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        widget.closeEvent(event)  # pylint: disable=no-member
        self.trigger_producer.unbind()

    def hideEvent(self, event: PySide2.QtGui.QHideEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        widget.hideEvent(event)  # pylint: disable=no-member
        if self.trigger_producer.is_bound():
            self.trigger_producer.hide(self._trigger_prefix + '.hide')
            self.trigger_producer.show(self._trigger_prefix + '.show')

    def showEvent(self, event: PySide2.QtGui.QShowEvent) -> None:
        widget = typing.cast(PySide2.QtWidgets.QWidget, super())
        # Pylint is ignoring the type cast.
        widget.showEvent(event)  # pylint: disable=no-member
        if self.trigger_producer.is_bound():
            self.trigger_producer.hide(self._trigger_prefix + '.show')
            self.trigger_producer.show(self._trigger_prefix + '.hide')
