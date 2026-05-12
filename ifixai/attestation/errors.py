class AttestationError(Exception):
    """Base class for HMAC attestation failures."""


class AttestationMissingError(AttestationError):
    """Structural response carries no signature field."""

    def __init__(self, hook: str) -> None:
        super().__init__(f"attestation_missing: {hook} returned no signature")
        self.hook = hook


class AttestationInvalidError(AttestationError):
    """Signature present but HMAC verification failed."""

    def __init__(self, hook: str) -> None:
        super().__init__(f"attestation_invalid: {hook} signature mismatch")
        self.hook = hook
