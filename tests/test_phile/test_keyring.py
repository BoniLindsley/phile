#!/usr/bin/env python3

# Standard libraries.
import unittest

# External dependencies.
import keyring

# Internal modules.
import phile.keyring


class TestMemoryKeyring(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.memory_keyring = phile.keyring.MemoryKeyring()

    def test_priority(self) -> None:
        self.assertEqual(phile.keyring.MemoryKeyring.priority, 2)

    def test_set_password(self) -> None:
        self.memory_keyring.set_password("s", "u", "p")

    def test_get_password_returns_none_if_not_found(self) -> None:
        self.assertIsNone(self.memory_keyring.get_password("s", "u"))

    def test_get_password_retrieves_password_set(self) -> None:
        self.memory_keyring.set_password("s", "u", "p")
        self.assertEqual(self.memory_keyring.get_password("s", "u"), "p")

    def test_delete_password_removes_password_set(self) -> None:
        self.memory_keyring.set_password("s", "u", "p")
        self.memory_keyring.delete_password("s", "u")
        self.assertIsNone(self.memory_keyring.get_password("s", "u"))

    def test_delete_password_ignores_missing_password(self) -> None:
        self.memory_keyring.delete_password("s", "u")

    def test_delete_password_keeps_service(self) -> None:
        self.memory_keyring.set_password("s", "u", "p")
        self.memory_keyring.set_password("s", "u1", "p1")
        self.memory_keyring.delete_password("s", "u")
        self.assertEqual(
            self.memory_keyring.get_password("s", "u1"), "p1"
        )

    def test_get_credential_retrieves_password_set(self) -> None:
        self.memory_keyring.set_password("s", "u", "p")
        credential = self.memory_keyring.get_credential("s", "u")
        assert credential is not None
        self.assertEqual(credential.username, "u")
        self.assertEqual(credential.password, "p")

    def test_get_credential_returns_first_username(self) -> None:
        self.memory_keyring.set_password("s", "u1", "p1")
        self.memory_keyring.set_password("s", "u2", "p2")
        credential = self.memory_keyring.get_credential("s", None)
        assert credential is not None
        self.assertEqual(credential.username, "u1")
        self.assertEqual(credential.password, "p1")

    def test_get_credential_ignores_missing_service(self) -> None:
        credential = self.memory_keyring.get_credential("s", "u")
        self.assertIsNone(credential)

    def test_get_credential_ignores_known_service_with_unknown_username(
        self,
    ) -> None:
        self.memory_keyring.set_password("s", "u", "p")
        credential = self.memory_keyring.get_credential("s", "u1")
        self.assertIsNone(credential)


class PreparesKeyring(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        keyring.set_keyring(  # type: ignore[no-untyped-call]
            phile.keyring.MemoryKeyring()
        )
