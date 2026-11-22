import importlib.util
from pathlib import Path

PATCH = Path(__file__).resolve().parents[1] / "history_export_patch.py"
SPEC = importlib.util.spec_from_file_location("history_export_patch", PATCH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_history_export_adds_authenticated_attachment_routes_and_is_idempotent():
    source = """
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
import os
app = FastAPI()
"""
    patched = MODULE.patch_main_source(source)
    assert '@app.post("/api/history/export")' in patched
    assert '@app.get("/api/history/export/{token}")' in patched
    assert "_authorized_user(x_telegram_init_data)" in patched
    assert "recent_scans(telegram_id, 1000000000)" in patched
    assert 'Content-Disposition' in patched
    assert 'antiscam-guardian-history.json' in patched
    assert "secrets.token_urlsafe(32)" in patched
    assert MODULE.patch_main_source(patched) == patched
