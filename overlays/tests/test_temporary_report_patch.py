import ast
import unittest

from app.temporary_report_patch import patch_main_source


class TemporaryReportPatchTests(unittest.TestCase):
    def test_injects_short_lived_single_use_download_routes(self):
        source = """from __future__ import annotations
from fastapi import FastAPI
app = FastAPI()
@app.get("/health")
def health():
    return {"ok": True}
"""
        patched = patch_main_source(source)
        ast.parse(patched)
        self.assertIn('@app.post("/api/reports")', patched)
        self.assertIn('@app.get("/api/reports/{token}"', patched)
        self.assertIn('secrets.token_urlsafe(24)', patched)
        self.assertIn('now + 120', patched)
        self.assertIn('_REPORT_DOWNLOADS.pop(token, None)', patched)
        self.assertIn('Access-Control-Allow-Origin', patched)
        self.assertIn('Content-Disposition', patched)
        self.assertLess(patched.index("from __future__ import annotations"), patched.index("import os"))

    def test_patch_is_idempotent(self):
        source = "from fastapi import FastAPI\\napp = FastAPI()\\n"
        once = patch_main_source(source)
        self.assertEqual(patch_main_source(once), once)

    def test_refuses_unknown_app_layout(self):
        with self.assertRaises(ValueError):
            patch_main_source("app = object()\\n")


if __name__ == "__main__":
    unittest.main()
