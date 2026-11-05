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
    verify_encrypted_sqlite_backup,
)
from app.restore_backup import restore as restore_backup


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

    def test_encrypted_sqlite_backup_can_be_fully_verified(self):
        database = self.root / "guardian.sqlite3"
        with sqlite3.connect(database) as conn:
            conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO scans(value) VALUES ('verified-record')")
        compressed = self.root / "guardian.sqlite3.gz"
        with gzip.open(compressed, "wb") as dst:
            dst.write(database.read_bytes())
        encrypted = self.root / "guardian.asgbak"
        encrypt_file(compressed, encrypted, self.key)
        verify_encrypted_sqlite_backup(encrypted, self.key)

        damaged = bytearray(encrypted.read_bytes())
        damaged[-1] ^= 0x01
        encrypted.write_bytes(damaged)
        with self.assertRaises(Exception):
            verify_encrypted_sqlite_backup(encrypted, self.key)

    def test_restore_utility_restores_and_checks_real_backup_file(self):
        source = self.root / "source.sqlite3"
        with sqlite3.connect(source) as conn:
            conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO scans(value) VALUES ('restore-me')")
        compressed = self.root / "source.sqlite3.gz"
        with gzip.open(compressed, "wb") as dst:
            dst.write(source.read_bytes())
        encrypted = self.root / "restore-test.asgbak"
        encrypt_file(compressed, encrypted, self.key)
        destination = self.root / "restored.sqlite3"
        with patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": self.key_text}, clear=False):
            restore_backup(encrypted, destination)
        with sqlite3.connect(destination) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT value FROM scans").fetchone()[0], "restore-me")

    def test_failed_restore_never_overwrites_existing_database(self):
        existing = self.root / "existing.sqlite3"
        with sqlite3.connect(existing) as conn:
            conn.execute("CREATE TABLE preserved (value TEXT)")
            conn.execute("INSERT INTO preserved VALUES ('keep-this')")
        compressed = self.root / "bad.sqlite3.gz"
        with gzip.open(compressed, "wb") as dst:
            dst.write(b"not a sqlite database")
        encrypted = self.root / "bad.asgbak"
        encrypt_file(compressed, encrypted, self.key)
        tampered = bytearray(encrypted.read_bytes())
        tampered[-1] ^= 0x01
        encrypted.write_bytes(tampered)
        with patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": self.key_text}, clear=False):
            with self.assertRaises(Exception):
                restore_backup(encrypted, existing, force=True)
        with sqlite3.connect(existing) as conn:
            self.assertEqual(conn.execute("SELECT value FROM preserved").fetchone()[0], "keep-this")

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
