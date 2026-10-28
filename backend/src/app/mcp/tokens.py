"""Access tokens (record 0006): make one, hash it, retire it.

A token is `sap_` plus 256 random bits. Only its SHA-256 digest is stored, so a database leak does
not reveal a usable token and a lost one can only be replaced. The plain token exists in memory
for the one response that shows it.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

PREFIX = "sap_"
# Longest bearer value the guard will hash: a real token is 4 + 43 characters.
MAX_TOKEN_LENGTH = 128


@dataclass(frozen=True, slots=True)
class NewToken:
    plain: str
    digest: bytes
    last4: str


def digest_of(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def new_token() -> NewToken:
    plain = PREFIX + secrets.token_urlsafe(32)
    return NewToken(plain=plain, digest=digest_of(plain), last4=plain[-4:])
