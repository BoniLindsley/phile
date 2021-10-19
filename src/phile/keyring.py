#!/usr/bin/env python3

# Standard libraries.
import typing

# External dependencies.
import keyring.backend
import keyring.credentials


class MemoryKeyring(keyring.backend.KeyringBackend):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(  # type: ignore[call-arg]
            *args, **kwargs
        )  # type: ignore[no-untyped-call]
        self.data: dict[str, dict[str, str]] = {}

    priority = 2

    def get_password(
        self,
        service: str,
        username: str,
    ) -> typing.Optional[str]:
        try:
            return self.data[service][username]
        except KeyError:
            return None

    def set_password(
        self, service: str, username: str, password: str
    ) -> None:
        service_data = self.data.setdefault(service, {})
        service_data[username] = password

    def delete_password(self, service: str, username: str) -> None:
        try:
            service_data = self.data[service]
            del service_data[username]
        except KeyError:
            return
        if not service_data:
            del self.data[service]

    def get_credential(
        self,
        service: str,
        username: typing.Optional[str],
    ) -> typing.Optional[keyring.credentials.SimpleCredential]:
        try:
            service_data = self.data[service]
        except KeyError:
            return None
        if username is None:
            username = next(iter(service_data.keys()))
        password = self.get_password(service, username)
        if password is None:
            return None
        SimpleCredential = keyring.credentials.SimpleCredential
        return SimpleCredential(  # type: ignore[no-untyped-call]
            username, password
        )
