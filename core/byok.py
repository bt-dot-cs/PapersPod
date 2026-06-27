"""BYOK (Bring Your Own Key) — encrypt/decrypt and store user API keys."""
from __future__ import annotations

import logging
import os

import psycopg

logger = logging.getLogger(__name__)


def _fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return Fernet(key.encode())


def encrypt_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def _hint(plaintext: str) -> str:
    """Return a safe display hint like 'sk-...ab12'."""
    if len(plaintext) <= 8:
        return "...****"
    return plaintext[:3] + "..." + plaintext[-4:]


def store_user_key(user_id: str, provider: str, plaintext_key: str, db_url: str) -> str:
    """Encrypt and upsert a user's API key. Returns the key hint."""
    encrypted = encrypt_key(plaintext_key)
    hint = _hint(plaintext_key)
    with psycopg.connect(db_url) as conn:
        conn.execute(
            """
            INSERT INTO user_api_keys (user_id, provider, encrypted_key, key_hint, active)
            VALUES (%s, %s, %s, %s, true)
            ON CONFLICT (user_id, provider)
            DO UPDATE SET encrypted_key = EXCLUDED.encrypted_key,
                          key_hint      = EXCLUDED.key_hint,
                          active        = true,
                          last_used_at  = NULL
            """,
            (user_id, provider, encrypted, hint),
        )
        conn.commit()
    logger.info("byok: stored key for user=%s provider=%s", user_id, provider)
    return hint


def get_user_key(user_id: str, provider: str, db_url: str) -> str | None:
    """Return decrypted user API key if active, else None. Updates last_used_at."""
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            """
            UPDATE user_api_keys
               SET last_used_at = now()
             WHERE user_id = %s AND provider = %s AND active = true
            RETURNING encrypted_key
            """,
            (user_id, provider),
        ).fetchone()
        conn.commit()
    if not row:
        return None
    return decrypt_key(row[0])


def deactivate_user_key(user_id: str, provider: str, db_url: str) -> bool:
    """Deactivate a user's API key. Returns True if a row was updated."""
    with psycopg.connect(db_url) as conn:
        cur = conn.execute(
            "UPDATE user_api_keys SET active = false WHERE user_id = %s AND provider = %s",
            (user_id, provider),
        )
        updated = cur.rowcount
        conn.commit()
    return updated > 0


def list_user_keys(user_id: str, db_url: str) -> list[dict]:
    """Return [{provider, key_hint, active, created_at, last_used_at}, ...]."""
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            """
            SELECT provider, key_hint, active, created_at, last_used_at
              FROM user_api_keys
             WHERE user_id = %s
             ORDER BY provider
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "provider":     r[0],
            "key_hint":     r[1],
            "active":       r[2],
            "created_at":   r[3].isoformat() if r[3] else None,
            "last_used_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]
