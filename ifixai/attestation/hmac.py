import hashlib
import hmac
import logging
import os
from hashlib import sha256
from typing import Protocol

from ifixai.attestation.errors import AttestationInvalidError, AttestationMissingError

_logger = logging.getLogger(__name__)

_ENV_KEY = "IFIXAI_ATTESTATION_KEY"

_missing_key_logged: bool = False


def _log_missing_key_once() -> None:
    """Emit a single info-level notice per process when the attestation key is unset.

    Structural runners call attestation checks dozens of times per suite; logging
    on every call drowns the operator output. Surface the condition once.
    """
    global _missing_key_logged
    if _missing_key_logged:
        return
    _missing_key_logged = True
    _logger.info(
        "%s not set — attestation checks will be skipped for this run", _ENV_KEY
    )


class Signable(Protocol):
    """Any structural return type that carries HMAC fields."""

    signature: bytes | None
    signed_payload: bytes | None


def load_attestation_key() -> bytes | None:
    """Read attestation key from env var (hex-encoded). Returns None if unset."""
    raw = os.environ.get(_ENV_KEY)
    if raw is None:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        _logger.error(
            "IFIXAI_ATTESTATION_KEY is set but not valid hex; attestation disabled"
        )
        return None


def key_fingerprint(key: bytes) -> str:
    """First 8 hex chars of sha256(key). Never logs the key itself."""
    return sha256(key).hexdigest()[:8]


def _build_message(nonce: str, test_id: str, request_id: str, payload: bytes) -> bytes:
    payload_digest = sha256(payload).digest()
    return nonce.encode() + test_id.encode() + request_id.encode() + payload_digest


def compute_signature(
    key: bytes,
    nonce: str,
    test_id: str,
    request_id: str,
    signed_payload: bytes,
) -> bytes:
    """Compute HMAC-SHA256 over (nonce | test_id | request_id | sha256(payload))."""
    msg = _build_message(nonce, test_id, request_id, signed_payload)
    return hmac.new(key, msg, hashlib.sha256).digest()


def verify_attestation(
    key: bytes,
    nonce: str,
    test_id: str,
    request_id: str,
    result: Signable,
    hook: str,
) -> None:
    """Verify HMAC on a structural result. Raises on failure.

    Raises AttestationMissingError if signature or signed_payload is None.
    Raises AttestationInvalidError if HMAC comparison fails.
    """
    if result.signature is None or result.signed_payload is None:
        raise AttestationMissingError(hook)
    expected = compute_signature(key, nonce, test_id, request_id, result.signed_payload)
    if not hmac.compare_digest(expected, result.signature):
        raise AttestationInvalidError(hook)


def check_attestation(
    result: Signable | None,
    nonce: str,
    test_id: str,
    request_id: str,
    hook: str,
) -> AttestationMissingError | AttestationInvalidError | None:
    """Convenience wrapper for runners.

    Loads key from env. If key absent, logs warning and returns None (skip).
    If key present and result is None, returns AttestationMissingError.
    Otherwise delegates to verify_attestation and returns any error caught.
    Returns None on success.
    """
    key = load_attestation_key()
    if key is None:
        _log_missing_key_once()
        return None

    if result is None:
        return AttestationMissingError(hook)

    try:
        verify_attestation(key, nonce, test_id, request_id, result, hook)
        return None
    except (AttestationMissingError, AttestationInvalidError) as exc:
        return exc


def check_list_attestation(
    records: list[Signable],
    nonce: str,
    test_id: str,
    request_id: str,
    hook: str,
) -> AttestationMissingError | AttestationInvalidError | None:
    """Check attestation on every record in a list. Returns first error found.

    All records share the same nonce/test_id/request_id; the signed_payload
    distinguishes individual records within the response.
    """
    key = load_attestation_key()
    if key is None:
        _log_missing_key_once()
        return None

    if not records:
        return None

    for record in records:
        try:
            verify_attestation(key, nonce, test_id, request_id, record, hook)
        except (AttestationMissingError, AttestationInvalidError) as exc:
            return exc

    return None
