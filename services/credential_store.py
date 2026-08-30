# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import ctypes
import ctypes.wintypes
import json
import os
import time
from pathlib import Path

_ENTROPY = b"SolarEconomy-CredStore-v1"
_VERSION = 1
_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _to_blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _blob_to_bytes(blob: _DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def _dpapi_protect(data: bytes) -> bytes | None:
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob, in_buf = _to_blob(data)
        entropy_blob, entropy_buf = _to_blob(_ENTROPY)
        out_blob = _DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            0,
            ctypes.byref(out_blob),
        )
        if not ok:
            return None
        try:
            return _blob_to_bytes(out_blob)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob, in_buf = _to_blob(data)
        entropy_blob, entropy_buf = _to_blob(_ENTROPY)
        out_blob = _DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            0,
            ctypes.byref(out_blob),
        )
        if not ok:
            return None
        try:
            return _blob_to_bytes(out_blob)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None


def _store_path() -> Path | None:
    try:
        local_app_data = os.getenv("LOCALAPPDATA")
        if not local_app_data:
            return None
        return Path(local_app_data) / "SolarEconomy" / "credentials.bin"
    except Exception:
        return None


def save_credentials(license_key: str, discord_id: int) -> bool:
    try:
        if not license_key or not discord_id:
            return False
        path = _store_path()
        if path is None:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "license_key": license_key,
            "discord_id": discord_id,
            "saved_at": time.time(),
            "version": _VERSION,
        }
        raw = json.dumps(payload).encode("utf-8")
        encrypted = _dpapi_protect(raw)
        if encrypted is None:
            return False
        path.write_bytes(encrypted)
        return True
    except Exception:
        return False


def load_credentials() -> dict | None:
    try:
        path = _store_path()
        if path is None or not path.exists():
            return None
        encrypted = path.read_bytes()
        if not encrypted:
            return None
        raw = _dpapi_unprotect(encrypted)
        if raw is None:
            return None
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if not payload.get("license_key") or not payload.get("discord_id") or not payload.get("saved_at"):
            return None
        age = time.time() - payload["saved_at"]
        if age > _MAX_AGE_SECONDS:
            clear_credentials()
            return None
        return payload
    except Exception:
        return None


def clear_credentials() -> bool:
    try:
        path = _store_path()
        if path is None:
            return False
        if path.exists():
            path.unlink()
        return True
    except Exception:
        return False


def has_credentials() -> bool:
    return load_credentials() is not None


def credentials_status() -> dict:
    try:
        path = _store_path()
        if path is None or not path.exists():
            return {"exists": False, "saved_at": None, "days_remaining": None, "discord_id": None}
        payload = load_credentials()
        if payload is None:
            return {"exists": False, "saved_at": None, "days_remaining": None, "discord_id": None}
        age = time.time() - payload["saved_at"]
        days_remaining = max(0, int((_MAX_AGE_SECONDS - age) // (24 * 60 * 60)))
        discord_id_str = str(payload["discord_id"])
        masked = discord_id_str[:2] + "*" * max(0, len(discord_id_str) - 4) + discord_id_str[-2:] if len(discord_id_str) > 4 else "*" * len(discord_id_str)
        return {
            "exists": True,
            "saved_at": payload["saved_at"],
            "days_remaining": days_remaining,
            "discord_id": masked,
        }
    except Exception:
        return {"exists": False, "saved_at": None, "days_remaining": None, "discord_id": None}
