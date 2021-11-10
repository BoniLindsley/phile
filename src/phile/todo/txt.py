#!/usr/bin/env python3

# Standard libraries.
import datetime
import logging
import pathlib

_logger = logging.getLogger(__name__)


def find_key_assignment(todo_entry: str, key: str) -> list[str]:
    # Precondition: todo_entry does not contain `\n`.
    # Precondition: todo_entry contains " $key=value".
    # Returns: ["before", " $key=", "value", "after"]
    assert "\n" not in todo_entry
    before, key_assignment, value = todo_entry.rpartition(
        " #" + key + "="
    )
    if not key_assignment:
        raise ValueError("Given task does not contain key: {key}.")
    space_index = value.find(" ")
    if space_index != -1:
        after = value[space_index:]
        value = value[:space_index]
    else:
        after = ""
    return [before, key_assignment, value, after]


def set_key(todo_entry: str, key: str, value: str) -> str:
    try:
        result = find_key_assignment(todo_entry, key)
    except ValueError:
        return "".join(
            (
                todo_entry,
                "" if todo_entry[-1] == " " else " ",
                "#",
                key,
                "=",
                value,
            )
        )
    result[2] = value
    return "".join(result)


def del_key(todo_entry: str, key: str) -> str:
    try:
        result = find_key_assignment(todo_entry, key)
    except ValueError:
        return todo_entry
    return "".join((result[0], result[3]))


def datetime_to_string(instant: datetime.datetime) -> str:
    return instant.strftime("%Y%m%dT%H%M%SZ")


def set_entry_key(
    todo_list: list[str], *, index: int, key: str, value: str
) -> None:
    try:
        todo_entry = todo_list[index]
    except IndexError as error:
        raise IndexError(
            f"Cannot get entry {index}."
            f" Zero-based. Total: {len(todo_list)}.",
        ) from error
    new_entry = set_key(todo_entry, key, value)
    todo_list[index] = new_entry


def load(todo_path: pathlib.Path) -> list[str]:
    _logger.debug("Loading todo from: %s", todo_path)
    try:
        file_content = todo_path.read_text()
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Cannot find todo path: {todo_path}"
        ) from error
    return file_content.splitlines()


def save(todo_path: pathlib.Path, *, todo_list: list[str]) -> None:
    _logger.debug("Saving todo to: %s", todo_path)
    todo_path.parent.mkdir(parents=True, exist_ok=True)
    with todo_path.open("w") as todo_file:
        for todo_entry in todo_list:
            print(todo_entry, file=todo_file)


def remove(todo_path: pathlib.Path, *, index: int) -> None:
    todo_list = load(todo_path)
    try:
        del todo_list[index]
    except IndexError as error:
        raise IndexError(
            f"Cannot remove entry {index}."
            f" Zero-based. Total: {len(todo_list)}.",
        ) from error
    save(todo_path, todo_list=todo_list)


def start(
    todo_path: pathlib.Path, *, index: int, now: datetime.datetime
) -> None:
    todo_list = load(todo_path)
    new_start = datetime_to_string(now)
    set_entry_key(
        todo_list, index=index, key="timetrack.start", value=new_start
    )
    save(todo_path, todo_list=todo_list)


def stop(
    todo_path: pathlib.Path, *, index: int, now: datetime.datetime
) -> None:
    todo_list = load(todo_path)
    new_start = datetime_to_string(now)
    set_entry_key(
        todo_list, index=index, key="timetrack.stop", value=new_start
    )
    save(todo_path, todo_list=todo_list)
