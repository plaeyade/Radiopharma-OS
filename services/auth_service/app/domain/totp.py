"""
TOTP — RFC 6238 (HMAC-SHA1, paso de 30 s, 6 dígitos) para el segundo factor
del Auth Service (EDS v2.0, cap. 47 IAM).

Sin dependencias externas: hmac + hashlib + base64 de la stdlib.

Anti-replay: `verify` devuelve el paso (contador de 30 s) del código aceptado
y rechaza cualquier paso <= `last_step`, de modo que un código ya usado no
puede reutilizarse dentro de su ventana de validez (§11.10(d) 21 CFR Part 11:
los controles de acceso deben impedir el reuso de credenciales).

Códigos de recuperación: 8 códigos de un solo uso ("XXXX-XXXX"), almacenados
como hash SHA-256 (nunca en claro, al igual que las contraseñas).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_S: int = 30
DIGITS: int = 6
WINDOW: int = 1            # pasos de deriva de reloj tolerados (±30 s)
SECRET_BYTES: int = 20     # 160 bits, recomendación RFC 4226
RECOVERY_N: int = 8
_ISSUER = "Radiopharma OS"


def new_secret() -> str:
    """Secreto TOTP aleatorio en base32 (sin padding), listo para otpauth://."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _decode(secret_b32: str) -> bytes:
    pad = "=" * (-len(secret_b32) % 8)
    return base64.b32decode(secret_b32.upper() + pad)


def hotp(secret_b32: str, counter: int) -> str:
    """HOTP RFC 4226 con truncamiento dinámico."""
    digest = hmac.new(_decode(secret_b32),
                      struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** DIGITS)).zfill(DIGITS)


def current_step(at_time: float | None = None) -> int:
    return int((time.time() if at_time is None else at_time) // STEP_S)


def totp(secret_b32: str, at_time: float | None = None) -> str:
    """Código TOTP del instante dado (ahora por defecto)."""
    return hotp(secret_b32, current_step(at_time))


def verify(secret_b32: str, code: str, at_time: float | None = None,
           window: int = WINDOW, last_step: int = -1) -> int | None:
    """Verifica un código con ventana de deriva y anti-replay.

    Devuelve el paso aceptado (siempre > last_step) o None si el código
    no es válido o corresponde a un paso ya consumido.
    """
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    step = current_step(at_time)
    for cand in range(step - window, step + window + 1):
        if cand <= last_step:
            continue                       # anti-replay: paso ya consumido
        if hmac.compare_digest(hotp(secret_b32, cand), code):
            return cand
    return None


def otpauth_uri(secret_b32: str, username: str,
                issuer: str = _ISSUER) -> str:
    """URI otpauth:// para enrolar en Google/Microsoft Authenticator, Aegis…"""
    label = quote(f"{issuer}:{username}", safe=":")
    return (f"otpauth://totp/{label}"
            f"?secret={secret_b32}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_S}")


# ------------------------------------------------------- códigos de respaldo

def new_recovery_codes(n: int = RECOVERY_N) -> list[str]:
    """Genera n códigos de un solo uso con formato 'XXXX-XXXX' (base32)."""
    out = []
    for _ in range(n):
        raw = base64.b32encode(secrets.token_bytes(5)).decode().rstrip("=")
        out.append(f"{raw[:4]}-{raw[4:]}")
    return out


def hash_recovery(code: str) -> str:
    """Hash SHA-256 del código normalizado (se almacena solo el hash)."""
    norm = code.strip().upper().replace(" ", "")
    return hashlib.sha256(norm.encode()).hexdigest()
