"""Minimal encrypted local persistence for sandbox tokens; replace with KMS-backed storage in AWS."""
from __future__ import annotations

import base64
import os
import sqlite3
import time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenStore:
    def __init__(self, path: str = "forecastops.db", key: str | None = None):
        raw = key or os.getenv("ENCRYPTION_KEY") or os.getenv("TOKEN_ENCRYPTION_KEY")
        if not raw:
            # Deliberately process-local in developer mode: connections cannot survive a restart.
            raw = base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()
        self.key = base64.urlsafe_b64decode(raw)
        self.path = Path(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS square_connections (merchant_id TEXT PRIMARY KEY, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS oauth_states (state_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL)")

    def _connect(self):
        return sqlite3.connect(self.path)

    def save(self, merchant_id: str, token: str) -> None:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key).encrypt(nonce, token.encode(), merchant_id.encode())
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO square_connections VALUES (?, ?, ?)", (merchant_id, nonce, ciphertext))

    def get(self, merchant_id: str) -> str | None:
        with self._connect() as db:
            record = db.execute("SELECT nonce, ciphertext FROM square_connections WHERE merchant_id = ?", (merchant_id,)).fetchone()
        return AESGCM(self.key).decrypt(record[0], record[1], merchant_id.encode()).decode() if record else None

    def issue_state(self, state_hash: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM oauth_states WHERE expires_at < ?", (time.time(),))
            db.execute("INSERT INTO oauth_states VALUES (?, ?)", (state_hash, time.time() + 600))

    def consume_state(self, state_hash: str) -> bool:
        with self._connect() as db:
            result = db.execute("DELETE FROM oauth_states WHERE state_hash = ? AND expires_at >= ?", (state_hash, time.time()))
            return result.rowcount == 1
