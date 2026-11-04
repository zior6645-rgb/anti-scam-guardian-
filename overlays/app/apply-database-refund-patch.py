from __future__ import annotations

import ast
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/database.py")
source = path.read_text(encoding="utf-8")
ast.parse(source)

migration_marker = '"ALTER TABLE star_entitlements ADD COLUMN starts_at TEXT"'
if migration_marker not in source:
    anchor = "        )\n\n\ndef upsert_user"
    migration = '''        )

        # Additive migration for correctly recomputing stacked paid periods after refunds.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(star_entitlements)")}
        if "starts_at" not in columns:
            conn.execute("ALTER TABLE star_entitlements ADD COLUMN starts_at TEXT")
        if "duration_days" not in columns:
            conn.execute("ALTER TABLE star_entitlements ADD COLUMN duration_days INTEGER NOT NULL DEFAULT 30")
        legacy_rows = conn.execute(
            "SELECT charge_id, expires_at, duration_days FROM star_entitlements WHERE starts_at IS NULL"
        ).fetchall()
        for legacy in legacy_rows:
            try:
                legacy_expiry = datetime.fromisoformat(legacy["expires_at"])
                legacy_start = legacy_expiry - timedelta(days=int(legacy["duration_days"] or 30))
            except (TypeError, ValueError):
                continue
            conn.execute(
                "UPDATE star_entitlements SET starts_at=? WHERE charge_id=?",
                (legacy_start.isoformat(), legacy["charge_id"]),
            )


def upsert_user'''
    if anchor not in source:
        raise SystemExit("Could not find init_db migration insertion point")
    source = source.replace(anchor, migration, 1)

old_insert = '''        conn.execute(
            "INSERT INTO star_entitlements(charge_id, telegram_id, expires_at) VALUES (?, ?, ?)",
            (charge_id, telegram_id, expiry),
        )'''
new_insert = '''        conn.execute(
            "INSERT INTO star_entitlements(charge_id, telegram_id, starts_at, duration_days, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (charge_id, telegram_id, base.isoformat(), days, expiry),
        )'''
if old_insert in source:
    source = source.replace(old_insert, new_insert, 1)
elif new_insert not in source:
    raise SystemExit("Could not find star entitlement insert")

refund_start = source.find("def record_star_refund(charge_id: str) -> bool:")
if refund_start < 0:
    raise SystemExit("Could not find record_star_refund")

refund_function = '''def record_star_refund(charge_id: str) -> bool:
    """Record a Stars refund and recompute the user's remaining paid periods.

    Future periods stacked behind a refunded period move forward. A period
    already in progress keeps its original end date.
    """
    now = _now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        charge = conn.execute(
            "SELECT telegram_id FROM star_charges WHERE charge_id=?", (charge_id,)
        ).fetchone()
        if not charge:
            return False

        cursor = conn.execute(
            "INSERT OR IGNORE INTO star_refunds(charge_id, processed_at) VALUES (?, ?)",
            (charge_id, now.isoformat()),
        )
        if cursor.rowcount != 1:
            return False

        telegram_id = int(charge["telegram_id"])
        rows = conn.execute(
            "SELECT e.charge_id, e.starts_at, e.duration_days, e.expires_at, c.created_at "
            "FROM star_entitlements e "
            "JOIN star_charges c ON c.charge_id=e.charge_id "
            "LEFT JOIN star_refunds r ON r.charge_id=e.charge_id "
            "WHERE e.telegram_id=? AND r.charge_id IS NULL "
            "ORDER BY c.created_at ASC, e.charge_id ASC",
            (telegram_id,),
        ).fetchall()

        cursor_expiry: datetime | None = None
        new_expiry = now
        for row in rows:
            try:
                original_expiry = datetime.fromisoformat(row["expires_at"])
                charge_created = datetime.fromisoformat(row["created_at"])
                duration_days = max(1, min(int(row["duration_days"] or 30), 3650))
                original_start = (
                    datetime.fromisoformat(row["starts_at"])
                    if row["starts_at"] else original_expiry - timedelta(days=duration_days)
                )
            except (TypeError, ValueError):
                continue

            if original_expiry <= now:
                continue

            if cursor_expiry is None:
                new_start = original_start if original_start <= now else now
            else:
                new_start = max(cursor_expiry, charge_created)

            adjusted_expiry = new_start + timedelta(days=duration_days)
            conn.execute(
                "UPDATE star_entitlements SET starts_at=?, expires_at=? WHERE charge_id=?",
                (new_start.isoformat(), adjusted_expiry.isoformat(), row["charge_id"]),
            )
            cursor_expiry = adjusted_expiry
            new_expiry = adjusted_expiry

        conn.execute(
            "INSERT INTO subscriptions(telegram_id, expires_at, source) VALUES (?, ?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET expires_at=excluded.expires_at, source=excluded.source",
            (telegram_id, new_expiry.isoformat(), "telegram_stars"),
        )
        return True
'''
source = source[:refund_start] + refund_function
ast.parse(source)
path.write_text(source, encoding="utf-8")
print(f"PATCHED {path}")
