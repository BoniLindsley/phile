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
import phile.capability


async def add_configuration(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_configuration(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile
            import phile.configuration
            with capability_registry.provide(
                await asyncio.to_thread(phile.configuration.load)
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.configuration',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    phile_configuration,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_hotkey_gui(
    capability_registry: phile.capability.Registry,
) -> None:
    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.hotkey.gui',
        phile.launcher.Descriptor(
            after={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            before={'phile_shutdown.target'},
            binds_to={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            conflicts={'phile_shutdown.target'},
            exec_start=[asyncio.get_running_loop().create_future],
        )
    )


async def add_hotkey_pynput(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run_pynput() -> None:
        import phile.configuration
        import phile.hotkey.pynput
        import phile.trigger
        await phile.hotkey.pynput.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            trigger_registry=(
                capability_registry[phile.trigger.Registry]
            ),
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_hotkey_pyside2(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.configuration
        import phile.PySide2.QtCore
        import phile.hotkey.pyside2
        import phile.trigger
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_launcher_cmd(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.cmd
        import phile.launcher.cmd

        await phile.cmd.async_cmdloop_threaded_stdin(
            phile.launcher.cmd.Cmd(
                launcher_registry=launcher_registry,
            )
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.launcher.cmd',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_log_file(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import phile.configuration
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_log_stderr(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import sys
            import phile.configuration
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_keyring(
    capability_registry: phile.capability.Registry,
) -> None:

    async def keyring_backend(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import keyring
            default_keyring = await asyncio.to_thread(
                keyring.get_keyring
            )
            with capability_registry.provide(
                default_keyring, keyring.backend.KeyringBackend
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'keyring',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    keyring_backend,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_tmux(
    capability_registry: phile.capability.Registry
) -> None:

    async def phile_tmux_control_mode(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
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
                with capability_registry.provide(
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tmux.control_mode',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    phile_tmux_control_mode,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_tray(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tray
            tray_registry = phile.tray.Registry()
            try:
                with capability_registry.provide(tray_registry):
                    ready.set_result(True)
                    await create_future()
            finally:
                tray_registry.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_tray_datetime(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import datetime
        import phile.tray.datetime
        import phile.tray.watchdog
        await phile.tray.datetime.run(
            tray_target=capability_registry[phile.tray.watchdog.Target],
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.datetime',
        phile.launcher.Descriptor(
            after={'phile.tray.watchdog'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.watchdog'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_tray_imap(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import keyring
        import phile.configuration
        import phile.tray.imapclient
        await phile.tray.imapclient.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            keyring_backend=capability_registry[
                # Use of abstract type as key is intended.
                keyring.backend.KeyringBackend  # type: ignore[misc]
            ],
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.imapclient',
        phile.launcher.Descriptor(
            after={'phile.configuration', 'keyring'},
            before={'phile_shutdown.target'},
            binds_to={'phile.configuration', 'keyring'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_tray_notify(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.configuration
        import phile.tray.notify
        import phile.tray.watchdog
        import phile.watchdog.asyncio
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_tray_psutil(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.tray.psutil
        import phile.tray.watchdog
        await phile.tray.psutil.run(
            tray_target=capability_registry[phile.tray.watchdog.Target],
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.psutil',
        phile.launcher.Descriptor(
            after={'phile.tray.watchdog'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.watchdog'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_tray_pyside2_window(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.PySide2.QtCore
        import phile.tray
        import phile.tray.pyside2_window
        pyside2_executor = (
            capability_registry[phile.PySide2.QtCore.Executor]
        )
        text_icons = capability_registry[phile.tray.TextIcons]
        await phile.tray.pyside2_window.run(
            pyside2_executor=pyside2_executor,
            text_icons=text_icons,
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.pyside2.window',
        phile.launcher.Descriptor(
            after={'phile.tray.text', 'pyside2'},
            before={'phile_shutdown.target'},
            binds_to={'phile.tray.text', 'pyside2'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_tray_text(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tray
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_tray_tmux(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.tmux.control_mode
        import phile.tray
        import phile.tray.tmux
        control_mode = (
            capability_registry[phile.tmux.control_mode.Client]
        )
        text_icons = capability_registry[phile.tray.TextIcons]
        await phile.tray.tmux.run(
            control_mode=control_mode,
            text_icons=text_icons,
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_tray_watchdog(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.configuration
            import phile.tray.watchdog
            import phile.watchdog.asyncio
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_trigger(
    capability_registry: phile.capability.Registry
) -> None:

    async def phile_trigger_registry(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.trigger
            with capability_registry.provide(phile.trigger.Registry()):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.trigger',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    phile_trigger_registry,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_trigger_launcher(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_trigger_launcher_producer(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.launcher
            import phile.trigger
            import phile.trigger.launcher
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.trigger.launcher',
        phile.launcher.Descriptor(
            after={'phile.trigger'},
            before={'phile_shutdown.target'},
            binds_to={'phile.trigger'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    phile_trigger_launcher_producer,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_trigger_watchdog(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        import phile.configuration
        import phile.trigger
        import phile.trigger.watchdog
        import phile.watchdog.asyncio
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
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


async def add_pyside2(
    capability_registry: phile.capability.Registry,
) -> None:

    async def pyside2(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
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
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'pyside2',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    pyside2,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_watchdog_asyncio_observer(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.watchdog.asyncio
            with capability_registry.provide(
                phile.watchdog.asyncio.Observer(),
                phile.watchdog.asyncio.BaseObserver,
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'watchdog.asyncio.observer',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_watchdog_observer(
    capability_registry: phile.capability.Registry,
) -> None:

    async def watchdog_observer(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import watchdog.observers
            import phile.trigger.watchdog
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

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'watchdog.observer',
        phile.launcher.Descriptor(
            before={'phile_shutdown.target'},
            conflicts={'phile_shutdown.target'},
            exec_start=[
                functools.partial(
                    watchdog_observer,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add(capability_registry: phile.capability.Registry) -> None:
    await add_configuration(capability_registry=capability_registry)
    await add_hotkey_gui(capability_registry=capability_registry)
    await add_hotkey_pynput(capability_registry=capability_registry)
    await add_hotkey_pyside2(capability_registry=capability_registry)
    await add_log_file(capability_registry=capability_registry)
    await add_log_stderr(capability_registry=capability_registry)
    await add_keyring(capability_registry=capability_registry)
    await add_launcher_cmd(capability_registry=capability_registry)
    await add_pyside2(capability_registry=capability_registry)
    await add_tmux(capability_registry=capability_registry)
    await add_tray(capability_registry=capability_registry)
    await add_tray_datetime(capability_registry=capability_registry)
    await add_tray_imap(capability_registry=capability_registry)
    await add_tray_notify(capability_registry=capability_registry)
    await add_tray_psutil(capability_registry=capability_registry)
    await add_tray_pyside2_window(
        capability_registry=capability_registry
    )
    await add_tray_text(capability_registry=capability_registry)
    await add_tray_tmux(capability_registry=capability_registry)
    await add_tray_watchdog(capability_registry=capability_registry)
    await add_trigger(capability_registry=capability_registry)
    await add_trigger_launcher(capability_registry=capability_registry)
    await add_trigger_watchdog(capability_registry=capability_registry)
    await add_watchdog_asyncio_observer(
        capability_registry=capability_registry
    )
    await add_watchdog_observer(capability_registry=capability_registry)
