"""Minimal TOTP (RFC 6238) for admin 2FA – no extra package required."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time


def generate_secret(length: int = 20) -> str:
    raw = os.urandom(length)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    # pad base32
    pad = (-len(s)) % 8
    s = s + ("=" * pad)
    return base64.b32decode(s, casefold=True)


def totp_code(secret: str, for_time: int | None = None, step: int = 30, digits: int = 6) -> str:
    if for_time is None:
        for_time = int(time.time())
    counter = for_time // step
    key = _normalize_secret(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not secret or not code:
        return False
    code = str(code).strip().replace(" ", "")
    if not code.isdigit():
        return False
    now = int(time.time())
    for w in range(-window, window + 1):
        if totp_code(secret, for_time=now + w * 30) == code.zfill(6) or totp_code(secret, for_time=now + w * 30) == code:
            return True
        # also compare without zfill mismatch
        if hmac.compare_digest(totp_code(secret, for_time=now + w * 30), code.zfill(6)):
            return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str = "Megha Hotel") -> str:
    from urllib.parse import quote
    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits=6&period=30"
    )
