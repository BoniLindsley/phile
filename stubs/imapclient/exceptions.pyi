# The alias-ed names are variables of type `type`
# rather than actual classes,
# even though they are classes in the code.
# This breaks inheritance.
IMAPClientError = Exception  # imaplib.IMAP4.error
IMAPClientAbortError = Exception  # imaplib.IMAP4.abort
IMAPClientReadOnlyError = Exception  # imaplib.IMAP4.readonly


class CapabilityError(IMAPClientError):
    ...


class LoginError(IMAPClientError):
    ...


class IllegalStateError(IMAPClientError):
    ...


class InvalidCriteriaError(IMAPClientError):
    ...


class ProtocolError(IMAPClientError):
    ...
