#!/usr/bin/env python3

# Standard library.
import asyncio
import cmd
import contextlib
import functools
import shlex
import sys
import typing

# Internal packages.
import phile
import phile.capability
import phile.cmd
import phile.launcher
import phile.main


class Cmd(cmd.Cmd):
    def __init__(
        self,
        *args: typing.Any,
        launcher_registry: phile.launcher.Registry,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._launcher_registry = launcher_registry
        self.known_launchers: list[str] = []
        self.launcher_ids: dict[str, int] = {}

    def do_EOF(self, arg: str) -> typing.Literal[True]:
        del arg
        return True

    def do_reset(self, arg: str) -> None:
        del arg
        self.known_launchers.clear()
        self.launcher_ids.clear()
        self.do_list("")

    def do_start(self, arg: str) -> None:
        argv = shlex.split(arg)
        launcher_ids: list[int] = []
        for entry in argv:
            try:
                launcher_id = int(entry)
            except ValueError:
                self.stdout.write(
                    "Unable to parse given launcher: {entry}\n".format(
                        entry=entry
                    )
                )
                return
            launcher_ids.append(launcher_id)
        known_launcher_count = len(self.known_launchers)
        for launcher_id in launcher_ids:
            if launcher_id >= known_launcher_count:
                self.stdout.write(
                    "Unknown launcher ID {launcher_id}.\n".format(
                        launcher_id=launcher_id
                    )
                )
                return
        for launcher_id in launcher_ids:
            launcher_name = self.known_launchers[launcher_id]
            self._launcher_registry.state_machine.start(launcher_name)
        self.stdout.write(
            "Started {count} launchers.\n".format(
                count=len(launcher_ids)
            )
        )

    def do_stop(self, arg: str) -> None:
        argv = shlex.split(arg)
        launcher_ids: list[int] = []
        for entry in argv:
            try:
                launcher_id = int(entry)
            except ValueError:
                self.stdout.write(
                    "Unable to parse given launcher: {entry}\n".format(
                        entry=entry
                    )
                )
                return
            launcher_ids.append(launcher_id)
        known_launcher_count = len(self.known_launchers)
        for launcher_id in launcher_ids:
            if launcher_id >= known_launcher_count:
                self.stdout.write(
                    "Unknown launcher ID {launcher_id}.\n".format(
                        launcher_id=launcher_id
                    )
                )
                return
        for launcher_id in launcher_ids:
            launcher_name = self.known_launchers[launcher_id]
            self._launcher_registry.state_machine.stop(launcher_name)
        self.stdout.write(
            "Stopped {count} launchers.\n".format(
                count=len(launcher_ids)
            )
        )

    def do_list(self, arg: str) -> None:
        del arg
        current_launchers = set(self._launcher_registry.database.type)
        for name in sorted(current_launchers):
            self._assign_id(name)
        self.stdout.write(
            "Listing IDs and states of {count} launchers.\n".format(
                count=len(current_launchers)
            )
        )
        is_running = self._launcher_registry.state_machine.is_running
        running_launchers = {
            name for name in current_launchers if is_running(name)
        }
        write = self.stdout.write
        for launcher_id, name in enumerate(self.known_launchers):
            if name in current_launchers:
                if name in running_launchers:
                    write(
                        "[running] {launcher_id}: {name}\n".format(
                            launcher_id=launcher_id, name=name
                        )
                    )
                else:
                    write(
                        "[stopped] {launcher_id}: {name}\n".format(
                            launcher_id=launcher_id, name=name
                        )
                    )

    def _assign_id(self, launcher: str) -> None:
        new_id = len(self.known_launchers)
        launcher_id = self.launcher_ids.setdefault(launcher, new_id)
        if launcher_id == new_id:
            self.known_launchers.append(launcher)
            assert self.known_launchers.index(launcher) == launcher_id
