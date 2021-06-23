#!/usr/bin/env python3
# pylint: disable=import-outside-toplevel
# pylint: disable=redefined-outer-name

# Function scope imports are used
# to ensure imports occur only when necessary.
# For example, the function may determine a launcher to be unusable
# in a certain platform, and not import it.
# Standard library.
import asyncio
import functools
import typing

# Internal packages.
import phile.launcher


def add_configuration(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile
            import phile.configuration
            with launcher_registry.capability_registry.provide(
                await asyncio.to_thread(phile.configuration.load)
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.configuration',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_hotkey_gui(launcher_registry: phile.launcher.Registry) -> None:
    launcher_registry.add_nowait(
        'phile.hotkey.gui',
        phile.launcher.Descriptor(
            after={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            before={'phile_shutdown.target'},
            binds_to={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            conflicts={'phile_shutdown.target'},
            exec_start=[asyncio.get_event_loop().create_future],
        )
    )


def add_hotkey_pynput(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def run_pynput() -> None:
        import phile.configuration
        import phile.hotkey.pynput
        import phile.trigger
        capability_registry = launcher_registry.capability_registry
        await phile.hotkey.pynput.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            trigger_registry=(
                capability_registry[phile.trigger.Registry]
            ),
        )

    launcher_registry.add_nowait(
        'phile.hotkey.pynput',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[run_pynput],
        )
    )


def add_hotkey_pyside2(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def run() -> None:
        import phile.configuration
        import phile.PySide2.QtCore
        import phile.hotkey.pyside2
        import phile.trigger
        capability_registry = launcher_registry.capability_registry
        configurations = (
            capability_registry[phile.configuration.Entries]
        )
        pyside2_executor = (
            capability_registry[phile.PySide2.QtCore.Executor]
        )
        trigger_registry = (capability_registry[phile.trigger.Registry])
        await phile.hotkey.pyside2.run(
            configurations=configurations,
            pyside2_executor=pyside2_executor,
            trigger_registry=trigger_registry,
        )

    launcher_registry.add_nowait(
        'phile.hotkey.pyside2',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
                'pyside2',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
                'pyside2',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_launcher_cmd(launcher_registry: phile.launcher.Registry) -> None:

    async def run() -> None:
        import phile.cmd
        import phile.launcher.cmd

        await phile.cmd.async_cmdloop_threaded_stdin(
            phile.launcher.cmd.Cmd(
                launcher_registry=launcher_registry,
            )
        )

    launcher_registry.add_nowait(
        'phile.launcher.cmd',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_log_file(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import phile.configuration
            capability_registry = launcher_registry.capability_registry
            configuration = (
                capability_registry[phile.configuration.Entries]
            )
            log_level = configuration.log_file_level
            log_path = (
                configuration.state_directory_path /
                configuration.log_file_path
            )
            handler = logging.FileHandler(str(log_path))
            try:
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(levelno)03d] %(name)s:'
                    ' %(message)s',
                )
                handler.setFormatter(formatter)
                handler.setLevel(log_level)
                package_logger = logging.getLogger('phile')
                package_logger.addHandler(handler)
                package_logger.setLevel(1)
                try:
                    ready.set_result(True)
                    await create_future()
                finally:
                    package_logger.removeHandler(handler)
            finally:
                handler.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.log.file',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            before={'phile_shutdown.target'},
            binds_to={'phile.configuration'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_log_stderr(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import sys
            import phile.configuration
            capability_registry = launcher_registry.capability_registry
            configuration = (
                capability_registry[phile.configuration.Entries]
            )
            log_level = configuration.log_stderr_level
            handler = logging.StreamHandler(sys.stderr)
            try:
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(levelno)03d] %(name)s:'
                    ' %(message)s',
                )
                handler.setFormatter(formatter)
                handler.setLevel(log_level)
                package_logger = logging.getLogger('phile')
                package_logger.addHandler(handler)
                package_logger.setLevel(1)
                try:
                    ready.set_result(True)
                    await create_future()
                finally:
                    package_logger.removeHandler(handler)
            finally:
                handler.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.log.stderr',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            before={'phile_shutdown.target'},
            binds_to={'phile.configuration'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_keyring(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import keyring
            default_keyring = await asyncio.to_thread(
                keyring.get_keyring
            )
            capability_registry = launcher_registry.capability_registry
            with capability_registry.provide(
                default_keyring, keyring.backend.KeyringBackend
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'keyring',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_tmux(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tmux.control_mode
            async with phile.tmux.control_mode.open(
                control_mode_arguments=(
                    phile.tmux.control_mode.Arguments()
                )
            ) as control_mode:
                with launcher_registry.capability_registry.provide(
                    control_mode, phile.tmux.control_mode.Client
                ):
                    async with phile.asyncio.open_task(
                        control_mode.run()
                    ):
                        ready.set_result(True)
                        await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.tmux.control_mode',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_tray(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tray
            tray_registry = phile.tray.Registry()
            try:
                with launcher_registry.capability_registry.provide(
                    tray_registry
                ):
                    ready.set_result(True)
                    await create_future()
            finally:
                tray_registry.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.tray',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_tray_datetime(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def run() -> None:
        import datetime
        import phile.tray.datetime
        import phile.tray.watchdog
        capability_registry = launcher_registry.capability_registry
        await phile.tray.datetime.run(
            tray_target=capability_registry[phile.tray.watchdog.Target],
        )

    launcher_registry.add_nowait(
        'phile.tray.datetime',
        phile.launcher.Descriptor(
            after={'phile.tray.watchdog'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.watchdog'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_tray_imap(launcher_registry: phile.launcher.Registry) -> None:

    async def run() -> None:
        import keyring
        import phile.configuration
        import phile.tray.imapclient
        capability_registry = launcher_registry.capability_registry
        await phile.tray.imapclient.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            keyring_backend=capability_registry[
                # Use of abstract type as key is intended.
                keyring.backend.KeyringBackend  # type: ignore[misc]
            ],
        )

    launcher_registry.add_nowait(
        'phile.tray.imapclient',
        phile.launcher.Descriptor(
            after={'phile.configuration', 'keyring'},
            before={'phile_shutdown.target'},
            binds_to={'phile.configuration', 'keyring'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_tray_notify(launcher_registry: phile.launcher.Registry) -> None:

    async def run() -> None:
        import phile.configuration
        import phile.tray.notify
        import phile.tray.watchdog
        import phile.watchdog.asyncio
        capability_registry = launcher_registry.capability_registry
        await phile.tray.notify.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            observer=(
                capability_registry[phile.watchdog.asyncio.BaseObserver]
            ),
            tray_target=(
                capability_registry[phile.tray.watchdog.Target]
            ),
        )

    launcher_registry.add_nowait(
        'phile.tray.notify',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.tray.watchdog',
                'watchdog.asyncio.observer',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.tray.watchdog',
                'watchdog.asyncio.observer',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_tray_psutil(launcher_registry: phile.launcher.Registry) -> None:

    async def run() -> None:
        import phile.tray.psutil
        import phile.tray.watchdog
        capability_registry = launcher_registry.capability_registry
        await phile.tray.psutil.run(
            tray_target=capability_registry[phile.tray.watchdog.Target],
        )

    launcher_registry.add_nowait(
        'phile.tray.psutil',
        phile.launcher.Descriptor(
            after={'phile.tray.watchdog'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.watchdog'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_tray_pyside2_window(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def run() -> None:
        import phile.PySide2.QtCore
        import phile.tray
        import phile.tray.pyside2_window
        capability_registry = launcher_registry.capability_registry
        pyside2_executor = (
            capability_registry[phile.PySide2.QtCore.Executor]
        )
        text_icons = capability_registry[phile.tray.TextIcons]
        await phile.tray.pyside2_window.run(
            pyside2_executor=pyside2_executor,
            text_icons=text_icons,
        )

    launcher_registry.add_nowait(
        'phile.tray.pyside2.window',
        phile.launcher.Descriptor(
            after={'phile.tray.text', 'pyside2'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.text', 'pyside2'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


def add_tray_text(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tray
            capability_registry = launcher_registry.capability_registry
            tray_registry = capability_registry[phile.tray.Registry]
            text_icons = phile.tray.TextIcons(
                tray_registry=tray_registry
            )
            try:
                with capability_registry.provide(text_icons):
                    ready.set_result(True)
                    await create_future()
            finally:
                await text_icons.aclose()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.tray.text',
        phile.launcher.Descriptor(
            after={'phile.tray'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_tray_tmux(launcher_registry: phile.launcher.Registry) -> None:

    async def run() -> None:
        import phile.tmux.control_mode
        import phile.tray
        import phile.tray.tmux
        capability_registry = launcher_registry.capability_registry
        control_mode = (
            capability_registry[phile.tmux.control_mode.Client]
        )
        text_icons = capability_registry[phile.tray.TextIcons]
        await phile.tray.tmux.run(
            control_mode=control_mode,
            text_icons=text_icons,
        )

    launcher_registry.add_nowait(
        'phile.tray.tmux',
        phile.launcher.Descriptor(
            after={
                'phile.tmux.control_mode',
                'phile.tray.text',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.tmux.control_mode',
                'phile.tray.text',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[run]
        )
    )


def add_tray_watchdog(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.configuration
            import phile.tray.watchdog
            import phile.watchdog.asyncio
            capability_registry = launcher_registry.capability_registry
            configuration = (
                capability_registry[phile.configuration.Entries]
            )
            observer = (
                capability_registry[phile.watchdog.asyncio.BaseObserver]
            )
            tray_registry = capability_registry[phile.tray.Registry]
            tray_target = phile.tray.watchdog.Target(
                configuration=configuration
            )
            async with phile.tray.watchdog.async_open(
                configuration=configuration,
                observer=observer,
                tray_registry=tray_registry,
            ) as tray_source:
                with capability_registry.provide(
                    tray_source
                ), capability_registry.provide(tray_target):
                    ready.set_result(True)
                    await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.tray.watchdog',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.tray',
                'watchdog.asyncio.observer',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.tray',
                'watchdog.asyncio.observer',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_trigger(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.trigger
            capability_registry = launcher_registry.capability_registry
            with capability_registry.provide(phile.trigger.Registry()):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.trigger',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_trigger_launcher(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.launcher
            import phile.trigger
            import phile.trigger.launcher
            capability_registry = launcher_registry.capability_registry
            trigger_registry = (
                capability_registry[phile.trigger.Registry]
            )
            async with phile.trigger.launcher.Producer(
                launcher_registry=launcher_registry,
                trigger_registry=trigger_registry,
            ) as producer:
                with capability_registry.provide(producer):
                    ready.set_result(True)
                    await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.trigger.launcher',
        phile.launcher.Descriptor(
            after={'phile.trigger'},
            before={'phile_shutdown.target'},
            binds_to={'phile.trigger'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_trigger_watchdog(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        import phile.configuration
        import phile.trigger
        import phile.trigger.watchdog
        import phile.watchdog.asyncio
        capability_registry = launcher_registry.capability_registry
        configuration = capability_registry[phile.configuration.Entries]
        observer = (
            capability_registry[phile.watchdog.asyncio.BaseObserver]
        )
        trigger_registry = capability_registry[phile.trigger.Registry]
        view = phile.trigger.watchdog.View(
            configuration=configuration,
            observer=observer,
            trigger_registry=trigger_registry,
        )
        loop = asyncio.get_running_loop()
        ready = loop.create_future()
        running_task = loop.create_task(view.run(ready=ready))
        await ready
        return running_task

    launcher_registry.add_nowait(
        'phile.trigger.watchdog',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'watchdog.asyncio.observer',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'watchdog.asyncio.observer',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        ),
    )


def add_pyside2(launcher_registry: phile.launcher.Registry) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        loop.stop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import PySide2.QtCore
            import PySide2.QtGui
            import PySide2.QtWidgets
            import phile.PySide2.QtCore
            import phile.launcher
            capability_registry = launcher_registry.capability_registry
            provide = capability_registry.provide
            qt_app = PySide2.QtWidgets.QApplication.instance()
            qt_app.setQuitLockEnabled(False)
            with provide(
                qt_app,
                PySide2.QtCore.QCoreApplication,
            ), provide(
                qt_app,
                PySide2.QtGui.QGuiApplication,
            ), provide(
                qt_app,
            ), phile.PySide2.QtCore.Executor(
            ) as pyside2_executor, provide(
                pyside2_executor,
            ):
                ready.set_result(True)
                try:
                    await create_future()
                finally:
                    launcher_registry.state_machine.start(
                        'phile_shutdown.target'
                    )
                    phile.PySide2.QtCore.call_soon_threadsafe(
                        qt_app.quit
                    )

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'pyside2',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_watchdog_asyncio_observer(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.watchdog.asyncio
            capability_registry = launcher_registry.capability_registry
            with capability_registry.provide(
                phile.watchdog.asyncio.Observer(),
                phile.watchdog.asyncio.BaseObserver,
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'watchdog.asyncio.observer',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add_watchdog_observer(
    launcher_registry: phile.launcher.Registry
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import watchdog.observers
            import phile.trigger.watchdog
            capability_registry = launcher_registry.capability_registry
            async with phile.watchdog.observers.async_open() as observer:
                with capability_registry.provide(
                    observer,
                    watchdog.observers.api.BaseObserver,
                ):
                    ready.set_result(True)
                    await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry.add_nowait(
        'watchdog.observer',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


def add(launcher_registry: phile.launcher.Registry) -> None:
    add_configuration(launcher_registry=launcher_registry)
    add_hotkey_gui(launcher_registry=launcher_registry)
    add_hotkey_pynput(launcher_registry=launcher_registry)
    add_hotkey_pyside2(launcher_registry=launcher_registry)
    add_log_file(launcher_registry=launcher_registry)
    add_log_stderr(launcher_registry=launcher_registry)
    add_keyring(launcher_registry=launcher_registry)
    add_launcher_cmd(launcher_registry=launcher_registry)
    add_pyside2(launcher_registry=launcher_registry)
    add_tmux(launcher_registry=launcher_registry)
    add_tray(launcher_registry=launcher_registry)
    add_tray_datetime(launcher_registry=launcher_registry)
    add_tray_imap(launcher_registry=launcher_registry)
    add_tray_notify(launcher_registry=launcher_registry)
    add_tray_psutil(launcher_registry=launcher_registry)
    add_tray_pyside2_window(launcher_registry=launcher_registry)
    add_tray_text(launcher_registry=launcher_registry)
    add_tray_tmux(launcher_registry=launcher_registry)
    add_tray_watchdog(launcher_registry=launcher_registry)
    add_trigger(launcher_registry=launcher_registry)
    add_trigger_launcher(launcher_registry=launcher_registry)
    add_trigger_watchdog(launcher_registry=launcher_registry)
    add_watchdog_asyncio_observer(launcher_registry=launcher_registry)
    add_watchdog_observer(launcher_registry=launcher_registry)
