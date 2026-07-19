"""
Hash de contraseñas PBKDF2-HMAC-SHA256 (stdlib, 100k iteraciones).
Formato: pbkdf2$<iteraciones>$<salt_hex>$<hash_hex>
"""
from __future__ import annotations

import hashlib
import hmac
import os

_ITERATIONS = 100_000
_ALGO = "pbkdf2"


class Pbkdf2Hasher:
    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
        return f"{_ALGO}${_ITERATIONS}${salt.hex()}${dk.hex()}"

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            algo, iters, salt_hex, hash_hex = password_hash.split("$")
            if algo != _ALGO:
                return False
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt_hex), int(iters))
            return hmac.compare_digest(dk.hex(), hash_hex)
        except (ValueError, TypeError):
            return False
