#!/usr/bin/env python3
"""
-----------------------------------------
Trigger manipulation using :mod:`tkinter`
-----------------------------------------
"""

# Standard libraries.
import asyncio
import contextlib
import pathlib
import sys
import tkinter
import tkinter.ttk
import typing

# External dependencies.
import watchdog.observers

# Internal modules.
import phile
import phile.watchdog


class Window:  # pragma: no cover

    def __init__(
        self, *args: typing.Any, trigger_root: pathlib.Path,
        trigger_suffix: str, **kwargs: typing.Any
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.trigger_root = trigger_root
        self.trigger_suffix = trigger_suffix
        self.target_event_loop = asyncio.get_running_loop()
        self.treeview: typing.Optional[tkinter.ttk.Treeview] = None
        self.item_ids: dict[pathlib.Path, int] = {}
        self.run_initialised = asyncio.Event()
        self.worker = asyncio.Task(asyncio.to_thread(self.run))

    def run(self) -> None:
        root = tkinter.Tk()
        self.treeview = treeview = (
            tkinter.ttk.Treeview(root, columns=('Status', 'Name'))
        )
        treeview.heading(column='#0', text='ID')
        treeview.heading(column='Status', text='Status')
        treeview.heading(column='Name', text='Name')
        treeview.column(column='#0', minwidth=0, stretch=False, width=0)
        treeview.pack(expand=1, fill=tkinter.BOTH)
        self.target_event_loop.call_soon_threadsafe(
            self.run_initialised.set
        )
        menu = tkinter.Menu(root)
        menu.add_command(
            label='Activate', command=self.activate
        )  # type: ignore[no-untyped-call]
        menu.add_command(
            label='Clear', command=self.clear_deleted
        )  # type: ignore[no-untyped-call]
        root.config(menu=menu)
        root.mainloop()
        del menu
        self.treeview = None
        del root
        self.item_ids.clear()

    def activate(self) -> None:
        if self.treeview is None:
            return
        treeview = self.treeview
        selected_sources = (
            pathlib.Path(treeview.set(item=item_id, column='Name'))
            for item_id in treeview.selection()
        )
        selected_paths = (
            self.trigger_root / source for source in selected_sources
        )
        for path in selected_paths:
            path.unlink(missing_ok=True)

    def clear_deleted(self) -> None:
        if self.treeview is None:
            return
        item_ids = self.item_ids
        treeview = self.treeview
        trigger_root = self.trigger_root
        deleted_sources = [
            source for source in item_ids
            if not (trigger_root / source).exists()
        ]
        deleted_ids = (
            item_ids.pop(source) for source in deleted_sources
        )
        treeview.delete(*deleted_ids)  # type: ignore[no-untyped-call]

    def update(self, path: pathlib.Path) -> None:
        if self.treeview is None:
            return
        relative_source = path.relative_to(self.trigger_root)
        if path.exists():
            self.insert(relative_source)
        else:
            self.delete(relative_source)

    def insert(self, source: pathlib.Path) -> None:
        assert self.treeview is not None
        item_id = self.item_ids.get(source)
        if item_id is None:
            self.item_ids[source] = self.treeview.insert(
                parent=self.item_ids.get(source.parent, ''),
                index=tkinter.END,
                values=('On', str(source)),
            )
        else:
            self.treeview.set(item=item_id, column='Status', value='On')

    def delete(self, source: pathlib.Path) -> None:
        assert self.treeview is not None
        try:
            item_id = self.item_ids[source]
        except KeyError:
            return
        self.treeview.set(item=item_id, column='Status', value='Off')

    def filter_source(self, source: pathlib.Path) -> bool:
        return (source.is_relative_to(
            self.trigger_root
        )) and (source.suffix == self.trigger_suffix)


async def run(
    capabilities: phile.Capabilities
) -> int:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    observer = capabilities[watchdog.observers.api.BaseObserver]
    trigger_root = configuration.trigger_root
    trigger_suffix = configuration.trigger_suffix
    window = Window(
        trigger_root=trigger_root, trigger_suffix=trigger_suffix
    )
    await window.run_initialised.wait()
    with phile.watchdog.Scheduler(
        path_filter=window.filter_source,
        path_handler=window.update,
        watch_recursive=True,
        watched_path=trigger_root,
        watching_observer=observer,
    ):
        for path in trigger_root.rglob('*' + trigger_suffix):
            window.update(path)
        await window.worker
    return 0


async def async_main(argv: list[str]) -> int:  # pragma: no cover
    del argv
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    async with phile.watchdog.observers.async_open() as observer:
        capabilities[watchdog.observers.api.BaseObserver] = observer
        await run(capabilities=capabilities)
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
