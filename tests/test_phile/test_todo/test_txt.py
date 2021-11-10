#!/usr/bin/env python3

# Standard libraries.
import datetime
import pathlib

# External dependencies.
import pytest

# Internal modules.
import phile.todo.txt


class TestFindKeyAssignment:
    def test_finds_assignment_in_middle_of_string(self) -> None:
        assert phile.todo.txt.find_key_assignment(
            "text #key=value ?", "key"
        ) == ["text", " #key=", "value", " ?"]

    def test_finds_assignment_at_end_of_string(self) -> None:
        assert phile.todo.txt.find_key_assignment(
            "text #key=value", "key"
        ) == ["text", " #key=", "value", ""]

    def test_raises_value_error_if_assignment_not_found(self) -> None:
        with pytest.raises(ValueError):
            phile.todo.txt.find_key_assignment(
                "key #wrong_key=wrong_value", "key"
            )


class TestSetKey:
    def test_changes_assignment_in_middle_of_string(self) -> None:
        assert (
            phile.todo.txt.set_key(
                "before #key=old_value after", "key", "value"
            )
            == "before #key=value after"
        )

    def test_adds_new_assignment_at_end_of_string(self) -> None:
        assert (
            phile.todo.txt.set_key(
                "before #key=old_value", "key", "value"
            )
            == "before #key=value"
        )


class TestDelKey:
    def test_removes_assignment_in_middle_of_string(self) -> None:
        assert (
            phile.todo.txt.del_key("before #key=value after", "key")
            == "before after"
        )

    def test_removes_assignment_at_end_of_string(self) -> None:
        assert (
            phile.todo.txt.del_key("before #key=value", "key")
            == "before"
        )

    def test_ignores_missing_assignment(self) -> None:
        assert (
            phile.todo.txt.del_key("before #wrong_key=value", "key")
            == "before #wrong_key=value"
        )


def test_datetime_to_string_returns_ical_format() -> None:
    instant = datetime.datetime(2001, 2, 3, 6, 7, 8)
    assert (
        phile.todo.txt.datetime_to_string(instant) == "20010203T060708Z"
    )


class TestSetEntryKey:
    def test_adds_new_key(self) -> None:
        todo_list = ["First", "Summary"]
        phile.todo.txt.set_entry_key(
            todo_list, index=1, key="hello", value="world"
        )
        assert todo_list[1] == "Summary #hello=world"

    def test_updates_existing_key(self) -> None:
        todo_list = ["Summary #hello=sky", "Last"]
        phile.todo.txt.set_entry_key(
            todo_list, index=0, key="hello", value="world"
        )
        assert todo_list[0] == "Summary #hello=world"

    def test_raises_if_out_of_bound(self) -> None:
        with pytest.raises(IndexError):
            phile.todo.txt.set_entry_key(
                ["Summary", "Last"], index=2, key="hello", value="world"
            )

    def test_raises_properly_on_empty_list(self) -> None:
        with pytest.raises(IndexError):
            phile.todo.txt.set_entry_key(
                [], index=0, key="hello", value="world"
            )


class TestLoad:
    def test_returns_list(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("First\nSummary\n")
        assert (
            phile.todo.txt.load(
                todo_path,
            )
            == ["First", "Summary"]
        )

    def test_raises_if_missing(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        with pytest.raises(FileNotFoundError):
            phile.todo.txt.load(todo_path)


class TestSave:
    def test_joins_with_newline(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        phile.todo.txt.save(todo_path, todo_list=["First", "Summary"])
        assert todo_path.read_text() == "First\nSummary\n"

    def test_creates_directory_if_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "dir" / "todo.txt"
        phile.todo.txt.save(todo_path, todo_list=["First", "Summary"])
        assert todo_path.read_text() == "First\nSummary\n"


class TestRemove:
    def test_removes_one_entry(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("First\nSummary\n")
        phile.todo.txt.remove(todo_path, index=0)
        assert todo_path.read_text() == "Summary\n"

    def test_raises_if_file_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        with pytest.raises(FileNotFoundError):
            phile.todo.txt.remove(todo_path, index=0)

    def test_raises_if_index_not_found(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("")
        with pytest.raises(IndexError):
            phile.todo.txt.remove(todo_path, index=0)


class TestStart:
    def test_adds_new_start_time(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("First\nSummary\n")
        phile.todo.txt.start(
            todo_path,
            index=1,
            now=datetime.datetime(2002, 2, 2, 2, 2, 2),
        )
        assert (
            todo_path.read_text()
            == "First\nSummary #timetrack.start=20020202T020202Z\n"
        )

    def test_updates_start_time(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("Summary #timetrack.start=??\nLast\n")
        phile.todo.txt.start(
            todo_path,
            index=0,
            now=datetime.datetime(2003, 3, 3, 3, 3, 3),
        )
        assert (
            todo_path.read_text()
            == "Summary #timetrack.start=20030303T030303Z\nLast\n"
        )


def test_stop_adds_stop_time(tmp_path: pathlib.Path) -> None:
    todo_path = tmp_path / "todo.txt"
    todo_path.write_text("First\nSummary\n")
    phile.todo.txt.stop(
        todo_path,
        index=1,
        now=datetime.datetime(2002, 2, 2, 2, 2, 2),
    )
    assert (
        todo_path.read_text()
        == "First\nSummary #timetrack.stop=20020202T020202Z\n"
    )
