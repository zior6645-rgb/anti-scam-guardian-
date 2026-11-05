from __future__ import annotations

import base64
import gzip
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.backup_supervisor import (
    _first_private_admin_id,
    create_sqlite_snapshot,
    decrypt_file,
    encrypt_file,
    run_backup_once,
)


class BackupSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = os.urandom(32)
        self.key_text = base64.urlsafe_b64encode(self.key).decode("ascii")

    def tearDown(self):
        self.temp.cleanup()

    def test_encrypt_decrypt_round_trip(self):
        original = self.root / "input.bin"
        encrypted = self.root / "backup.asgbak"
        restored = self.root / "restored.bin"
        original.write_bytes(os.urandom(120_000))
        encrypt_file(original, encrypted, self.key)
        decrypt_file(encrypted, restored, self.key)
        self.assertEqual(original.read_bytes(), restored.read_bytes())

    def test_tampered_backup_is_rejected(self):
        original = self.root / "input.bin"
        encrypted = self.root / "backup.asgbak"
        restored = self.root / "restored.bin"
        original.write_bytes(b"sensitive database bytes")
        encrypt_file(original, encrypted, self.key)
        contents = bytearray(encrypted.read_bytes())
        contents[25] ^= 0x01
        encrypted.write_bytes(contents)
        with self.assertRaises(Exception):
            decrypt_file(encrypted, restored, self.key)
        self.assertFalse(restored.exists())

    def test_sqlite_snapshot_is_consistent_and_integrity_checked(self):
        source = self.root / "source.sqlite3"
        snapshot = self.root / "snapshot.sqlite3"
        with sqlite3.connect(source) as conn:
            conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO scans(value) VALUES ('test-record')")
        create_sqlite_snapshot(source, snapshot)
        with sqlite3.connect(snapshot) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT value FROM scans").fetchone()[0], "test-record")

    def test_admin_selection_ignores_group_ids(self):
        self.assertEqual(_first_private_admin_id("-100123, 456789"), 456789)
        with self.assertRaises(RuntimeError):
            _first_private_admin_id("-100123")

    def test_run_backup_uploads_encrypted_database_to_first_private_admin(self):
        database = self.root / "guardian.sqlite3"
        with sqlite3.connect(database) as conn:
            conn.execute("CREATE TABLE test_data (value TEXT)")
            conn.execute("INSERT INTO test_data VALUES ('private-value')")
        uploaded = self.root / "uploaded.asgbak"

        def fake_send(token, chat_id, document_path, caption):
            uploaded.write_bytes(document_path.read_bytes())
            self.assertEqual(token, "test-token")
            self.assertEqual(chat_id, 123456)
            self.assertIn("encrypted automatic SQLite backup", caption)
            return {"ok": True, "result": {"message_id": 42}}

        env = {
            "BOT_TOKEN": "test-token",
            "ADMIN_TELEGRAM_IDS": "-100987654,123456",
            "BACKUP_ENCRYPTION_KEY": self.key_text,
            "DATABASE_PATH": str(database),
            "BACKUP_INTERVAL_SECONDS": "86400",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "app.backup_supervisor.send_telegram_document", side_effect=fake_send
        ):
            result = run_backup_once()

        self.assertEqual(result["message_id"], 42)
        self.assertEqual(result["chat_id"], 123456)
        compressed = self.root / "restored.sqlite3.gz"
        decrypt_file(uploaded, compressed, self.key)
        restored = self.root / "restored.sqlite3"
        with gzip.open(compressed, "rb") as src, restored.open("wb") as dst:
            dst.write(src.read())
        with sqlite3.connect(restored) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT value FROM test_data").fetchone()[0], "private-value")


if __name__ == "__main__":
    unittest.main()
